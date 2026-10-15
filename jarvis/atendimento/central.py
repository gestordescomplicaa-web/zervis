"""A Central de Atendimento: o WhatsApp e o agente num processo próprio, sempre ligado (ADR 0031).

Roda como `python -m jarvis.atendimento`, de preferência num serviço do usuário
(`zervis-atendimento`, subido pelo Zé). Reiniciar o Zé, inclusive para aplicar melhorias, não
derruba o atendimento: o WhatsApp continua conectado e o agente continua respondendo.

- **API local** (`127.0.0.1`, porta livre escrita em `<estado>/atendimento.json`), com o token de
  `<config>/atendimento.token` (0600) em todo pedido. É por ela que o Zé mostra o WhatsApp,
  conecta, desconecta, devolve conversas e lê os eventos.
- **Eventos** (passou para você, mensagem para os avisos de lead quente) ficam numa fila curta no
  SQLite, numerados; o Zé busca com espera longa (`/eventos?depois=N`). Quem passou para você
  também fica no banco, que a página mostra mesmo se o evento se perder.
- A versão (`versao()`) é a impressão digital do código do atendimento: o Zé reinicia a Central
  quando ela muda, para nunca atender com código velho depois de uma atualização.
"""

import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
import os
import secrets
import signal
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from jarvis import lugares
from jarvis.atendimento import agente, ligacao, projeto, whatsapp

log = logging.getLogger(__name__)

TOKEN = lugares.CONFIG / "atendimento.token"
ESTADO = lugares.ESTADO / "atendimento.json"
EVENTOS = 200
AQUECER_S = 60.0  # confere se a persona ou o cérebro mudaram (a reserva antiga não serve)
ESPERA_EVENTOS_S = 25.0
CORPO_MAXIMO = 64 * 1024


def versao(pasta: Path = Path(__file__).parent) -> str:
    """Muda quando o código do atendimento muda (o Go tem a própria impressão, em whatsapp.py)."""
    h = hashlib.sha256()
    for arquivo in sorted(pasta.glob("*.py")):
        h.update(arquivo.name.encode() + b"\0" + arquivo.read_bytes())
    return h.hexdigest()[:16]


def garantir_token(arquivo: Path = TOKEN) -> str:
    """O segredo entre o Zé e a Central; criado uma vez, só o dono lê."""
    try:
        if texto := arquivo.read_text().strip():
            return texto
    except OSError:
        pass
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    novo = secrets.token_hex(32)
    temporario = arquivo.with_suffix(".next")
    temporario.touch(mode=0o600)
    temporario.write_text(novo)
    temporario.replace(arquivo)
    return novo


class Eventos:
    """Fila numerada; persistente na Central, isolada em memória nos testes da fila."""

    def __init__(self, tamanho: int = EVENTOS, registros: agente.Registros | None = None) -> None:
        self.registros = registros
        self.tamanho = tamanho
        self._fila: list[dict[str, Any]] = []
        self._ultimo = 0
        self._mudou = threading.Condition()

    def publicar(self, tipo: str, **dados: Any) -> None:
        with self._mudou:
            if self.registros is not None:
                self.registros.publicar_evento(tipo, dados, self.tamanho)
            else:
                self._ultimo += 1
                self._fila.append(
                    {"id": self._ultimo, "tipo": tipo, "quando": time.time(), **dados}
                )
                self._fila = self._fila[-self.tamanho :]
            self._mudou.notify_all()

    def _ler(self, visto: int) -> tuple[list[dict[str, Any]], int]:
        if self.registros is not None:
            return self.registros.eventos(visto)
        if visto > self._ultimo:
            visto = 0
        return [e for e in self._fila if e["id"] > visto], self._ultimo

    def depois(self, visto: int, espera: float = 0.0) -> tuple[list[dict[str, Any]], int]:
        fim = time.monotonic() + espera
        with self._mudou:
            while True:
                lista, ultimo = self._ler(visto)
                restante = fim - time.monotonic()
                if lista or restante <= 0:
                    return lista, ultimo
                self._mudou.wait(min(restante, 0.2))


class Central:
    def __init__(
        self,
        criar_motor: Callable[[], agente.Motor],
        wa: whatsapp.WhatsApp | None = None,
        atendente: agente.Atendente | None = None,
        avisos_ligados: Callable[[], bool] | None = None,
        motor_de_voz: Callable[[], Any] | None = None,
        chave_deepgram: Callable[[], str | None] | None = None,
    ) -> None:
        self.versao = versao()  # a do código com que esta Central subiu
        if avisos_ligados is None:
            from jarvis.avisos import mensagens  # só o arquivo da escolha; nada do núcleo

            avisos_ligados = mensagens.escolhido
        self.avisos_ligados = avisos_ligados
        self.motor_de_voz = motor_de_voz or _motor_de_voz
        self.chave_deepgram = chave_deepgram or _chave_deepgram
        self.ligacoes: set[str] = set()  # as chamadas em andamento
        # Pré-aquecimento (como o `prewarm` do Ligatia): a saudação já sintetizada e um motor
        # iniciado esperando a próxima ligação; a ligação começa sem esperar nenhum dos dois.
        self.saudacao: tuple[str, bytes] | None = None
        self.reserva: tuple[Any, str] | None = None  # (motor aquecido, o que ele recebeu)
        self.whatsapp = wa or whatsapp.WhatsApp(
            self._recebida,
            lambda: self.avisos_ligados() or agente.ler().ligado,
            ao_chamar=self._chamada_chegou,
        )
        self.atendente = atendente or agente.Atendente(
            criar_motor, self.whatsapp.enviar, self._passou, perfil=projeto.perfil
        )
        self.eventos = Eventos(registros=self.atendente.registros)
        self._servidor: ThreadingHTTPServer | None = None

    # --- o que chega do WhatsApp e do agente -------------------------------------------------

    def _recebida(self, r: whatsapp.Recebida) -> None:
        if not r.de_mim and self.avisos_ligados():
            self.eventos.publicar("mensagem", nome=r.nome, texto=r.texto)
        self.atendente.receber(r)

    def _passou(self, nome: str, motivo: str) -> None:
        self.eventos.publicar("passou", nome=nome, motivo=motivo)

    # --- ligações -------------------------------------------------------------------------

    def _chamada_chegou(self, evento: dict[str, Any]) -> None:
        """Do fio do WaCalls: a decisão e a ligação rodam no laço do atendente."""
        self.atendente.agendar(self.atender_ligacao(evento))

    def vai_atender(self, telefone: str, chamada: str) -> str | None:
        """Por que não atender (o celular segue tocando), ou None para atender."""
        p = self.atendente.perfil
        if not p.ligacoes or not self.atendente.atende(telefone, p):
            return "fora das regras"
        if self.atendente.registros.pausado(telefone):
            return "conversa com você"
        if chamada in self.ligacoes or len(self.ligacoes) >= ligacao.LIGACOES_JUNTAS:
            return "ocupado"
        if not self.chave_deepgram() or not ligacao.voz_pronta():
            return "sem escuta ou voz"
        return None

    async def aquecer(self) -> None:
        p = self.atendente.perfil
        if not p.ligacoes or not ligacao.voz_pronta():
            return
        texto = ligacao.saudacao(p)
        if self.saudacao is None or self.saudacao[0] != texto:
            pcm = await asyncio.to_thread(ligacao.falar_com_piper, ligacao.normalizar_voz(texto))
            self.saudacao = (texto, pcm)
        chave = json.dumps([ligacao.sistema(p), p.cerebro], ensure_ascii=False)
        if self.reserva is not None and self.reserva[1] == chave:
            return  # sem renovar por tempo: cada aquecimento é uma chamada ao modelo
        self._soltar_reserva()
        motor = self.motor_de_voz()
        await ligacao.aquecer_motor(motor, ligacao.sistema(p), texto)
        self.reserva = (motor, chave)
        log.info("central: ligação pré-aquecida")

    def _soltar_reserva(self) -> None:
        if self.reserva is not None:
            motor, _ = self.reserva
            self.reserva = None
            self.atendente.agendar(motor.fechar())

    def _tomar_reserva(self, p: agente.Perfil) -> tuple[Any, bool]:
        """O motor pré-aquecido, se ainda serve para esta persona e este cérebro."""
        chave = json.dumps([ligacao.sistema(p), p.cerebro], ensure_ascii=False)
        if self.reserva is not None and self.reserva[1] == chave:
            motor, _ = self.reserva
            self.reserva = None
            return motor, True
        self._soltar_reserva()
        return self.motor_de_voz(), False

    async def _aquecer_sempre(self) -> None:
        while True:
            try:
                await self.aquecer()
            except Exception:
                log.exception("central: pré-aquecimento falhou")
            await asyncio.sleep(AQUECER_S)

    async def atender_ligacao(self, evento: dict[str, Any]) -> None:
        sessao, chamada = str(evento.get("sessionId", "")), str(evento.get("id", ""))
        telefone = agente.numero(str(evento.get("phone", "")))
        if (motivo := self.vai_atender(telefone, chamada)) is not None:
            log.info("central: ligação não atendida (%s)", motivo)
            return
        from websockets.asyncio.client import connect

        self.ligacoes.add(chamada)
        inicio = time.monotonic()
        desfecho = "falha"
        try:
            await asyncio.to_thread(self.whatsapp.atender, sessao, chamada)
            url, cabecalho = self.whatsapp.audio(sessao, chamada)
            p = self.atendente.perfil
            motor, iniciado = self._tomar_reserva(p)
            pronta = (
                self.saudacao[1]
                if self.saudacao and self.saudacao[0] == ligacao.saudacao(p)
                else None
            )
            async with connect(url, additional_headers=cabecalho, max_size=None) as conexao:
                ouvido = ligacao.Ouvido(str(self.chave_deepgram()))
                await ouvido.abrir()
                desfecho = await ligacao.Chamada(
                    conexao,
                    ouvido,
                    motor,
                    p,
                    telefone,
                    "",
                    self.atendente.registros,
                    self._passou,
                    iniciado=iniciado,
                    saudacao_pronta=pronta,
                ).atender()
        except Exception:
            log.exception("central: a ligação falhou")
        finally:
            self.ligacoes.discard(chamada)
            with contextlib.suppress(Exception):
                await asyncio.to_thread(self.whatsapp.desligar, sessao, chamada)
            self.atendente.registros.ligacao(telefone, desfecho, time.monotonic() - inicio)
            self.eventos.publicar("ligacao", telefone=telefone, desfecho=desfecho)
            log.info("central: ligação encerrada (%s)", desfecho)
            self.atendente.agendar(self.aquecer())  # a próxima ligação já começa aquecida

    # --- a API ----------------------------------------------------------------------------

    def responder(self, metodo: str, caminho: str, corpo: dict[str, Any]) -> tuple[int, Any]:
        url = urlsplit(caminho)
        rota = (metodo, url.path)
        if rota == ("GET", "/saude"):
            return 200, {"versao": self.versao, "pid": os.getpid()}
        if rota == ("GET", "/whatsapp"):
            return 200, self.whatsapp.para_tela()
        if rota == ("POST", "/whatsapp/conectar"):
            self.whatsapp.conectar_em_segundo_plano()
            return 200, {}
        if rota == ("POST", "/whatsapp/desconectar"):
            self.whatsapp.desconectar()
            return 200, {}
        if rota == ("GET", "/pausados"):
            return 200, {"pausados": self.atendente.registros.pausados()}
        if rota == ("POST", "/devolver"):
            self.atendente.registros.devolver(str(corpo.get("telefone", "")))
            return 200, {}
        if rota == ("GET", "/eventos"):
            consulta = parse_qs(url.query)
            visto = int((consulta.get("depois") or ["0"])[0] or 0)
            espera = min(float((consulta.get("espera") or ["0"])[0] or 0), ESPERA_EVENTOS_S)
            lista, ultimo = self.eventos.depois(visto, espera)
            return 200, {"eventos": lista, "ultimo": ultimo}
        return 404, {"erro": "rota desconhecida"}

    def servir(self, token: str, porta: int = 0) -> int:
        central = self

        class Pedido(BaseHTTPRequestHandler):
            def log_message(self, formato: str, *args: Any) -> None:
                return

            def _enviar(self, codigo: int, dados: Any) -> None:
                corpo = json.dumps(dados, ensure_ascii=False).encode()
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

            def _tratar(self, metodo: str) -> None:
                recebido = self.headers.get("X-Atendimento-Token", "")
                if not hmac.compare_digest(recebido.encode(), token.encode()):
                    self._enviar(401, {"erro": "token"})
                    return
                corpo: Any = {}
                tamanho = int(self.headers.get("Content-Length") or 0)
                if tamanho > CORPO_MAXIMO:
                    self._enviar(413, {})
                    return
                if tamanho:
                    try:
                        corpo = json.loads(self.rfile.read(tamanho))
                    except ValueError:
                        self._enviar(400, {"erro": "json"})
                        return
                try:
                    codigo, dados = central.responder(
                        metodo, self.path, corpo if isinstance(corpo, dict) else {}
                    )
                except whatsapp.WhatsAppErro as erro:
                    codigo, dados = 409, {"erro": str(erro)}
                except Exception:
                    log.exception("central: pedido falhou")
                    codigo, dados = 500, {"erro": "falha interna"}
                self._enviar(codigo, dados)

            def do_GET(self) -> None:
                self._tratar("GET")

            def do_POST(self) -> None:
                self._tratar("POST")

        self._servidor = ThreadingHTTPServer(("127.0.0.1", porta), Pedido)
        self._servidor.daemon_threads = True
        threading.Thread(target=self._servidor.serve_forever, name="central", daemon=True).start()
        return int(self._servidor.server_address[1])

    def iniciar(self) -> None:
        self._aquecimento = self.atendente.agendar(self._aquecer_sempre())
        if whatsapp.escolhido():
            try:
                self.whatsapp.iniciar()
            except whatsapp.WhatsAppErro as erro:
                log.warning("central: o WhatsApp não subiu: %s", erro)

    def parar(self) -> None:
        if self._servidor is not None:
            self._servidor.shutdown()
            self._servidor.server_close()
        self.whatsapp.parar()
        self.atendente.parar()


def _motor_de_voz() -> Any:
    """O cérebro escolhido para o agente (página Atendimento); um por ligação."""
    from jarvis.atendimento import cerebro

    return cerebro.criar(projeto.perfil().cerebro, lugares.DADOS / "atendente-voz")


def _chave_deepgram() -> str | None:
    from jarvis import config
    from jarvis.voz import deepgram

    try:
        return deepgram.ler_chave(config.carregar().caminho("escuta", "chave_deepgram"))
    except Exception:
        return None


def _motor() -> agente.Motor:
    from jarvis.atendimento import cerebro

    motor: agente.Motor = cerebro.criar(
        projeto.perfil().cerebro, lugares.DADOS / "atendente-modelo"
    )
    return motor


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    token = garantir_token()
    central = Central(_motor)
    porta = central.servir(token)
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps({"porta": porta, "pid": os.getpid(), "versao": central.versao}))
    log.info("central de atendimento na porta local %d", porta)
    central.iniciar()
    fim = threading.Event()
    for sinal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sinal, lambda *_: fim.set())
    while not fim.wait(3600):
        pass
    central.parar()
    log.info("central de atendimento encerrada")
