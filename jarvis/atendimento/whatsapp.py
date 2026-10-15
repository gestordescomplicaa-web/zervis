"""O WhatsApp do atendimento: o WaCalls dentro do Zé (ADR 0031, etapa 1).

O WaCalls (Go, MIT; ver THIRD_PARTY.md) pareia o número pelo QR e mantém a conexão, com as
ligações e as mensagens. O código vem junto do Zé (`jarvis/atendimento/wacalls/`): na primeira vez
o Zé o compila com o Go da máquina, e compila de novo quando o código-fonte muda.

- Ele escuta só no endereço local e exige um token novo a cada subida: a interface dele controla o
  número e não tem login próprio.
- Os segredos do WhatsApp ficam em `<dados>/whatsapp/wacalls.db` (0600, criado pelo WaCalls).
- As mensagens recebidas chegam por um receptor local, com o token derivado de outro segredo da
  subida. O WaCalls só guarda e entrega uma mensagem quando `capturar()` diz que sim; fora disso,
  nada fica.
- O Zé só envia a resposta do agente de atendimento (`enviar`), a quem escreveu antes.
"""

import collections
import contextlib
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from jarvis import lugares
from jarvis.filho import Filho

log = logging.getLogger(__name__)

FONTE = Path(__file__).with_name("wacalls")
PASTA = lugares.DADOS / "whatsapp"
ESCOLHA = lugares.CONFIG / "whatsapp.json"
REGISTRO = lugares.ESTADO / "whatsapp.log"
NOME_DO_APARELHO = "Zérvis"  # o que aparece em "Aparelhos conectados" no celular
ROTULO = "agente-voz/interno/v1:"  # a derivação do token do receptor, a mesma do WaCalls
TEMPO_COMPILAR_S = 900  # a primeira compilação baixa os módulos do Go
CORPO_MAXIMO = 2 * 1024 * 1024
VISTOS = 2000  # a fila do WaCalls reenvia o que não foi confirmado: os ids recentes deduplicam
CLIENTE = "zervis-atendente"  # quem atende as chamadas no WaCalls
_CAPTURA = re.compile(r"/api/interno/whatsapp/captura/[0-9a-f]{1,64}")


class WhatsAppErro(RuntimeError):
    """Mensagem curta, pronta para a tela."""


@dataclass(frozen=True)
class Recebida:
    id: str
    nome: str  # como a pessoa se identifica no WhatsApp, ou o número
    telefone: str
    texto: str
    de_mim: bool = False  # enviada por este número (pelo celular ou pelo próprio agente)
    chat: str = ""  # o JID da conversa (só conversa privada chega até aqui)


_PRIVADO = re.compile(r"\d{5,20}(?::\d+)?@(?:s\.whatsapp\.net|lid)")  # número ou LID


def privado(chat: str) -> bool:
    """Só conversa com uma pessoa. Grupo, status, canal e qualquer tipo novo ficam de fora
    (pedido de 14/10/2026: o atendimento nunca responde em grupo)."""
    return _PRIVADO.fullmatch(chat or "") is not None


def escolhido(arquivo: Path = ESCOLHA) -> bool:
    try:
        return bool(json.loads(arquivo.read_text()).get("ativo"))
    except (OSError, ValueError, AttributeError):
        return False


def escolher(ativo: bool, arquivo: Path = ESCOLHA) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".next")
    temporario.write_text(json.dumps({"ativo": ativo}))
    temporario.replace(arquivo)


def impressao(fonte: Path = FONTE) -> str:
    """Muda quando o código-fonte muda: o binário compilado leva este nome."""
    h = hashlib.sha256()
    arquivos = (p for p in fonte.rglob("*") if p.is_file())
    for f in sorted(a for a in arquivos if a.suffix == ".go" or a.name in ("go.mod", "go.sum")):
        h.update(f.relative_to(fonte).as_posix().encode() + b"\0" + f.read_bytes())
    return h.hexdigest()[:16]


def binario(pasta: Path = PASTA, fonte: Path = FONTE) -> Path | None:
    alvo = pasta / "bin" / f"wacalls-{impressao(fonte)}"
    return alvo if alvo.is_file() else None


def go() -> str | None:
    return shutil.which("go")


def compilar(
    pasta: Path = PASTA, fonte: Path = FONTE, executar: Callable[..., Any] = subprocess.run
) -> Path:
    """O binário pronto para usar; compila com o Go da máquina se ainda não houver."""
    if (pronto := binario(pasta, fonte)) is not None:
        return pronto
    programa = go()
    if programa is None:
        raise WhatsAppErro("Go não encontrado.")
    destino = pasta / "bin"
    destino.mkdir(parents=True, exist_ok=True, mode=0o700)
    alvo = destino / f"wacalls-{impressao(fonte)}"
    temporario = alvo.with_suffix(".compilando")
    log.info("whatsapp: compilando o WaCalls")
    r = executar(
        [programa, "build", "-trimpath", "-o", str(temporario), "./cmd/server"],
        cwd=fonte,
        env={**os.environ, "CGO_ENABLED": "0"},
        capture_output=True,
        text=True,
        timeout=TEMPO_COMPILAR_S,
        check=False,
    )
    if r.returncode != 0 or not temporario.is_file():
        log.warning("whatsapp: a compilação falhou: %s", (r.stderr or "").strip()[-500:])
        temporario.unlink(missing_ok=True)
        raise WhatsAppErro("Não foi possível preparar o WhatsApp.")
    temporario.replace(alvo)
    for antigo in destino.glob("wacalls-*"):
        if antigo != alvo:
            antigo.unlink(missing_ok=True)
    return alvo


def token_interno(segredo: str) -> str:
    return hashlib.sha256((ROTULO + segredo).encode()).hexdigest()


def numero(jid: str) -> str:
    """O número de um JID ("5511999990000:12@s.whatsapp.net" -> "5511999990000")."""
    achado = re.match(r"\d+", jid or "")
    return achado.group(0) if achado else ""


def recebidas(corpo: Any) -> list[Recebida]:
    """As mensagens de texto de um lote do WaCalls, recebidas e enviadas; mídia fica de fora."""
    itens = corpo.get("mensagens") if isinstance(corpo, dict) else None
    saida = []
    for m in itens if isinstance(itens, list) else []:
        if not isinstance(m, dict) or m.get("type") != "text":
            continue
        if m.get("direction") not in ("inbound", "outbound"):
            continue
        chat = str(m.get("chat_jid") or "")
        if not privado(chat):
            continue
        texto = str(m.get("content") or "").strip()
        if not texto:
            continue
        telefone = str(m.get("phone") or "")
        nome = " ".join(str(m.get("push_name") or "").split()) or telefone or "um contato"
        de_mim = m.get("direction") == "outbound"
        saida.append(Recebida(str(m.get("event_id") or ""), nome, telefone, texto, de_mim, chat))
    return saida


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Receptor:
    """O endereço local por onde o WaCalls pergunta se pode guardar e entrega as mensagens."""

    def __init__(
        self,
        token: str,
        capturar: Callable[[], bool],
        ao_receber: Callable[[list[Recebida]], None],
    ) -> None:
        self.token = token
        self.capturar = capturar
        self.ao_receber = ao_receber
        self._vistos: collections.OrderedDict[str, None] = collections.OrderedDict()
        self._trava = threading.Lock()
        self._servidor: ThreadingHTTPServer | None = None

    def iniciar(self) -> int:
        receptor = self

        class Pedido(BaseHTTPRequestHandler):
            def log_message(self, formato: str, *args: Any) -> None:
                return

            def _responder(self, codigo: int, dados: dict[str, Any]) -> None:
                corpo = json.dumps(dados).encode()
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

            def _autorizado(self) -> bool:
                recebido = self.headers.get("X-Internal-Token", "")
                if hmac.compare_digest(recebido.encode(), receptor.token.encode()):
                    return True
                self._responder(401, {"erro": "token"})
                return False

            def do_GET(self) -> None:
                if not self._autorizado():
                    return
                if not _CAPTURA.fullmatch(self.path):
                    self._responder(404, {})
                    return
                self._responder(200, {"capturar": bool(receptor.capturar())})

            def do_POST(self) -> None:
                if not self._autorizado():
                    return
                if self.path != "/api/interno/whatsapp/mensagens":
                    self._responder(404, {})
                    return
                tamanho = int(self.headers.get("Content-Length") or 0)
                if not 0 < tamanho <= CORPO_MAXIMO:
                    self._responder(413, {})
                    return
                try:
                    corpo = json.loads(self.rfile.read(tamanho))
                except ValueError:
                    self._responder(400, {})
                    return
                novas = receptor._novas(recebidas(corpo))
                self._responder(200, {"recebidas": len(novas)})
                if novas:
                    try:
                        receptor.ao_receber(novas)
                    except Exception:
                        log.exception("whatsapp: mensagem recebida não tratada")

        self._servidor = ThreadingHTTPServer(("127.0.0.1", 0), Pedido)
        self._servidor.daemon_threads = True
        threading.Thread(
            target=self._servidor.serve_forever, name="whatsapp-receptor", daemon=True
        ).start()
        return int(self._servidor.server_address[1])

    def _novas(self, lista: list[Recebida]) -> list[Recebida]:
        novas = []
        with self._trava:
            for r in lista:
                if r.id and r.id in self._vistos:
                    continue
                if r.id:
                    self._vistos[r.id] = None
                    while len(self._vistos) > VISTOS:
                        self._vistos.popitem(last=False)
                novas.append(r)
        return novas

    def parar(self) -> None:
        if self._servidor is not None:
            self._servidor.shutdown()
            self._servidor.server_close()
            self._servidor = None


class WhatsApp:
    """O WaCalls como processo filho do Zé, e o que a tela precisa saber dele."""

    def __init__(
        self,
        ao_receber: Callable[[Recebida], None],
        capturar: Callable[[], bool],
        pasta: Path = PASTA,
        fonte: Path = FONTE,
        abrir: Callable[..., Any] = urllib.request.urlopen,
        ao_chamar: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.ao_receber = ao_receber
        self.ao_chamar = ao_chamar  # uma ligação chegando (evento "incoming" do WaCalls)
        self.capturar = capturar
        self.pasta = pasta
        self.fonte = fonte
        self.abrir = abrir
        self.preparando = False
        self.pedido = False  # "Conectar" em andamento: a tela segue acompanhando
        self.falha = ""
        self.porta = 0
        self.token = ""
        self.filho: Filho | None = None
        self.receptor: Receptor | None = None
        self._trava = threading.Lock()

    @property
    def ativo(self) -> bool:
        return self.filho is not None

    def disponivel(self) -> bool:
        return go() is not None or binario(self.pasta, self.fonte) is not None

    def iniciar(self) -> None:
        """Compila se preciso (pode levar minutos na primeira vez) e sobe o WaCalls."""
        with self._trava:
            if self.filho is not None or self.preparando:
                return
            self.preparando = True
        try:
            programa = compilar(self.pasta, self.fonte)
        except WhatsAppErro as erro:
            self.falha = str(erro)
            raise
        finally:
            self.preparando = False
        with self._trava:
            if self.filho is not None:
                return
            segredo = secrets.token_hex(32)
            self.token = secrets.token_hex(32)
            self.receptor = Receptor(token_interno(segredo), self.capturar, self._recebidas)
            porta_receptor = self.receptor.iniciar()
            self.porta = porta_livre()
            self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.filho = Filho(
                "whatsapp",
                [
                    str(programa),
                    "-addr", f"127.0.0.1:{self.porta}",
                    "-db", str(self.pasta / "wacalls.db"),
                    "-max-calls-per-session", "4",
                ],
                {
                    "WACALLS_INTERNAL_TOKEN": self.token,
                    "INTERNAL_TOKEN": segredo,
                    "DASHBOARD_URL": f"http://127.0.0.1:{porta_receptor}",
                    "WA_DEVICE_NAME": NOME_DO_APARELHO,
                },
                registro=REGISTRO,
            )  # fmt: skip
            self.filho.iniciar()
            if self.ao_chamar is not None:
                filho = self.filho
                threading.Thread(
                    target=self._ouvir_chamadas,
                    args=(filho,),
                    name="whatsapp-chamadas",
                    daemon=True,
                ).start()
            self.falha = ""
            log.info("whatsapp: WaCalls na porta local %d", self.porta)

    def parar(self) -> None:
        with self._trava:
            filho, self.filho = self.filho, None
            receptor, self.receptor = self.receptor, None
        if filho is not None:
            filho.parar()
        if receptor is not None:
            receptor.parar()

    def _ouvir_chamadas(self, filho: Filho) -> None:
        """Os eventos do WaCalls (SSE) enquanto esta subida durar; só "incoming" interessa."""
        while self.filho is filho:
            pedido = urllib.request.Request(
                f"http://127.0.0.1:{self.porta}/api/events",
                headers={"X-Internal-Token": self.token, "X-Client-Id": CLIENTE},
            )
            try:
                with self.abrir(pedido, timeout=60) as resposta:
                    for linha in resposta:
                        if self.filho is not filho:
                            return
                        texto = linha.decode(errors="replace").strip()
                        if not texto.startswith("data:"):
                            continue
                        with contextlib.suppress(ValueError):
                            evento = json.loads(texto[5:])
                            if isinstance(evento, dict) and evento.get("type") == "incoming":
                                assert self.ao_chamar is not None  # noqa: S101 (conferido acima)
                                self.ao_chamar(evento)
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(1.0)

    def atender(self, sessao: str, chamada: str) -> None:
        self._api("POST", f"/api/sessions/{sessao}/calls/{chamada}/accept", {}, espera=15.0)

    def desligar(self, sessao: str, chamada: str) -> None:
        self._api("DELETE", f"/api/sessions/{sessao}/calls/{chamada}", espera=10.0)

    def audio(self, sessao: str, chamada: str) -> tuple[str, dict[str, str]]:
        """O WebSocket do áudio da chamada (PCM 16 kHz) e o cabeçalho que ele exige."""
        url = f"ws://127.0.0.1:{self.porta}/api/sessions/{sessao}/calls/{chamada}/pcm"
        return url, {"X-Internal-Token": self.token, "X-Client-Id": CLIENTE}

    def _recebidas(self, lista: list[Recebida]) -> None:
        for r in lista:
            self.ao_receber(r)

    def _api(self, metodo: str, caminho: str, corpo: Any = None, espera: float = 5.0) -> Any:
        if not self.ativo:
            raise WhatsAppErro("WhatsApp desligado.")
        dados = None if corpo is None else json.dumps(corpo).encode()
        pedido = urllib.request.Request(
            f"http://127.0.0.1:{self.porta}{caminho}",
            data=dados,
            method=metodo,
            headers={
                "X-Internal-Token": self.token,
                "Content-Type": "application/json",
                "X-Client-Id": CLIENTE,
            },
        )
        try:
            with self.abrir(pedido, timeout=espera) as resposta:
                bruto = resposta.read()
        except (urllib.error.URLError, OSError) as erro:
            raise WhatsAppErro("Sem conexão com o WhatsApp.") from erro
        try:
            return json.loads(bruto) if bruto else {}
        except ValueError as erro:
            raise WhatsAppErro("Sem conexão com o WhatsApp.") from erro

    def sessoes(self) -> list[dict[str, Any]]:
        lista = self._api("GET", "/api/sessions").get("sessions")
        return [s for s in lista if isinstance(s, dict)] if isinstance(lista, list) else []

    def _aguardar(self, prazo_s: float = 15.0) -> list[dict[str, Any]]:
        fim = time.monotonic() + prazo_s
        while True:
            try:
                return self.sessoes()
            except WhatsAppErro:
                if time.monotonic() > fim:
                    raise
                time.sleep(0.2)

    def para_tela(self) -> dict[str, Any]:
        """Estado: preparando, indisponivel, desligado, iniciando, desconectado, aguardando
        (o QR está na tela), conectando ou conectado."""
        if self.preparando or (self.pedido and not self.ativo):
            return {"estado": "preparando"}
        if not self.ativo:
            estado = "desligado" if self.disponivel() else "indisponivel"
            return {"estado": estado, "falha": self.falha}
        try:
            sessoes = self.sessoes()
        except WhatsAppErro:
            return {"estado": "iniciando"}
        if not sessoes:
            return {"estado": "iniciando" if self.pedido else "desconectado"}
        s = sessoes[0]
        if s.get("paired") and s.get("state") == "open":
            return {"estado": "conectado", "numero": numero(str(s.get("jid", "")))}
        if s.get("state") == "qr" and s.get("qr"):
            return {"estado": "aguardando", "qr": str(s["qr"])}
        return {"estado": "conectando" if s.get("paired") else "desconectado"}

    def conectar(self) -> None:
        """Sobe o WaCalls (se preciso) e pede um QR para parear o número."""
        self.iniciar()
        escolher(True)
        sessoes = self._aguardar()
        if not sessoes:
            self._api("POST", "/api/sessions", {"name": NOME_DO_APARELHO}, espera=15.0)
            return
        s = sessoes[0]
        if not s.get("paired") and s.get("state") != "qr":
            self._api("POST", f"/api/sessions/{s['id']}/pair", {}, espera=15.0)

    def enviar(self, telefone: str, texto: str, chave: str) -> str:
        """Envia um texto ao número; devolve o id do evento (`<sessão>:<mensagem>`), o mesmo que
        volta pelo receptor como mensagem enviada. A `chave` evita o envio em dobro."""
        if not re.fullmatch(r"\d{8,15}", telefone):
            raise WhatsAppErro("Destino inválido.")  # só um número: nunca um grupo
        sessoes = [s for s in self.sessoes() if s.get("paired") and s.get("state") == "open"]
        if not sessoes:
            raise WhatsAppErro("WhatsApp não conectado.")
        sid = str(sessoes[0]["id"])
        r = self._api(
            "POST",
            f"/api/sessions/{sid}/messages",
            {
                "kind": "atendimento_reply",
                "phones": [telefone],
                "text": texto,
                "idempotency_key": chave,
            },
            espera=30.0,
        )
        if not r.get("acknowledged"):
            raise WhatsAppErro("Mensagem não enviada.")
        return f"{sid}:{r.get('message_id', '')}"

    def conectar_em_segundo_plano(self) -> None:
        """`conectar` sem prender quem pediu; a falha fica em `falha`, para a tela."""
        self.falha = ""
        self.pedido = True

        def conectar() -> None:
            try:
                self.conectar()
            except WhatsAppErro as erro:
                self.falha = str(erro)
                log.warning("whatsapp: não conectou: %s", erro)
            finally:
                self.pedido = False

        threading.Thread(target=conectar, name="whatsapp-conectar", daemon=True).start()

    def desconectar(self) -> None:
        """Sai do WhatsApp neste computador e apaga o pareamento."""
        self.iniciar()
        for s in self._aguardar():
            self._api("DELETE", f"/api/sessions/{s['id']}", espera=15.0)
        escolher(False)
        self.parar()
