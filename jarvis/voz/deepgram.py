"""Escuta em streaming pelo Deepgram nova-3 (ADR 0012; o mesmo do LIGATIA).

O áudio vai sendo transcrito enquanto o usuário fala; quando o segmentador fecha o pedido, um
`Finalize` devolve o resto em frações de segundo, em vez dos ~2 s do Whisper depois do fim.

Privacidade: uma conexão por pedido, aberta só depois do "Hey Orca" (ou na conversa contínua e na
resposta de uma confirmação) e fechada no fim do pedido; o "Hey Orca" nunca sai da máquina. A
chave vem só do arquivo `~/.config/zervis/deepgram.key` (600), que o painel grava, e não vai para
log. Conta nova: https://console.deepgram.com/signup
"""

import json
import logging
import queue
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

log = logging.getLogger(__name__)
ENDERECO = "wss://api.deepgram.com/v1/listen"
PROJETOS = "https://api.deepgram.com/v1/projects"  # só para conferir se a chave vale
CADASTRO = "https://console.deepgram.com/signup"
PARAMETROS = {
    "model": "nova-3",
    "language": "pt-BR",
    "encoding": "linear16",
    "sample_rate": 16000,
    "channels": 1,
    "interim_results": "true",
    "punctuate": "true",
    "smart_format": "false",  # "um Codex" virava "1 Codex"
}
# Palavras que o reconhecimento deve preferir (keyterm do nova-3): sem isto, "Ei Zé" virava
# "Reis é" e "Hey Zé" virava "Pois é" (gravações do chamado, 13/10/2026).
TERMOS = ("Zé", "Ei Zé", "Hey Zé", "Zérvis")
FINALIZAR = object()
FECHAR = object()


def consulta() -> str:
    return urlencode([*PARAMETROS.items(), *(("keyterm", t) for t in TERMOS)])


class EscutaErro(RuntimeError):
    pass


def ler_chave(arquivo: Path) -> str | None:
    try:
        chave = arquivo.read_text().strip()
    except OSError:
        return None
    return chave or None


def gravar_chave(arquivo: Path, chave: str) -> None:
    """A chave colada no painel: arquivo 0600 numa pasta 0700, escrita atômica."""
    chave = chave.strip()
    if not chave or len(chave) > 400 or any(c.isspace() for c in chave):
        raise ValueError("chave vazia ou com espaços")
    arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporario = arquivo.with_suffix(".next")
    temporario.touch(mode=0o600)
    temporario.chmod(0o600)
    temporario.write_text(chave + "\n")
    temporario.replace(arquivo)


def conferir(chave: str, abrir: Callable[..., Any] = urllib.request.urlopen) -> tuple[bool, str]:
    """Pergunta ao Deepgram se a chave vale, sem gastar crédito (lista os projetos da conta)."""
    pedido = urllib.request.Request(PROJETOS, headers={"Authorization": f"Token {chave}"})
    try:
        with abrir(pedido, timeout=10):
            return True, "Chave válida."
    except urllib.error.HTTPError as erro:
        if erro.code in (401, 403):
            return False, "Chave inválida."
        return False, f"Erro do Deepgram ({erro.code})."
    except OSError:
        return False, "Sem conexão com o Deepgram."


def _conectar_websocket(url: str, chave: str) -> Any:
    from websockets.sync.client import connect

    return connect(
        url, additional_headers={"Authorization": f"Token {chave}"}, open_timeout=5, close_timeout=2
    )


# O que o Deepgram responde ao recusar a conexão; o registro dizia só "InvalidStatus".
RECUSAS = {
    400: "pedido recusado (HTTP 400)",
    401: "chave inválida (HTTP 401)",
    402: "sem crédito no Deepgram (HTTP 402)",
    403: "chave sem permissão (HTTP 403)",
    429: "limite de conexões do Deepgram (HTTP 429)",
}
DEFINITIVOS = {400, 401, 402, 403}


def _status(erro: BaseException) -> int | None:
    resposta = getattr(erro, "response", None)
    codigo = getattr(resposta, "status_code", None)
    return codigo if isinstance(codigo, int) else None


def motivo(erro: BaseException) -> str:
    codigo = _status(erro)
    if codigo is None:
        return type(erro).__name__
    return RECUSAS.get(codigo, f"HTTP {codigo}")


class EscutaDeepgram:
    """Um pedido: abre, recebe os quadros, finaliza e devolve o texto."""

    def __init__(
        self, chave: str, conectar: Callable[[str, str], Any] = _conectar_websocket
    ) -> None:
        self.chave = chave
        self.conectar = conectar
        self.saida: queue.Queue[Any] = queue.Queue()
        self.finais: list[str] = []
        self.parcial = ""
        self.finalizado = threading.Event()
        self.erro: str | None = None
        self.segundos = 0.0  # áudio enviado (o Deepgram cobra por isto)
        self._ws: Any = None
        threading.Thread(target=self._rodar, name="deepgram", daemon=True).start()

    def enviar(self, pcm: bytes) -> None:
        self.segundos += len(pcm) / 32000
        self.saida.put(pcm)

    def ate_agora(self) -> str:
        """O que já foi reconhecido neste pedido, com o trecho ainda provisório."""
        return " ".join(t for t in (*self.finais, self.parcial) if t).strip()

    def terminar(self, limite_s: float = 3.0) -> str:
        """Pede o resto ao Deepgram e devolve o texto do pedido; `EscutaErro` se não vier."""
        self.saida.put(FINALIZAR)
        if not self.finalizado.wait(limite_s) or self.erro:
            self.cancelar()
            raise EscutaErro(self.erro or "o Deepgram não finalizou a tempo")
        self.cancelar()
        return " ".join(t for t in self.finais if t).strip()

    def cancelar(self) -> None:
        self.saida.put(FECHAR)

    # --- conexão (thread própria) -------------------------------------------------------------

    def _rodar(self) -> None:
        # Uma segunda tentativa: na VPS (16/10/2026) a conexão foi recusada quatro vezes seguidas
        # e voltou sozinha; chave e crédito não melhoram tentando de novo.
        for tentativa in range(2):
            try:
                self._ws = self.conectar(f"{ENDERECO}?{consulta()}", self.chave)
                break
            except Exception as erro:
                self.erro = f"conexão: {motivo(erro)}"
                if tentativa or _status(erro) in DEFINITIVOS:
                    self.finalizado.set()
                    return
                time.sleep(0.3)
        self.erro = None
        threading.Thread(target=self._receber, name="deepgram-rx", daemon=True).start()
        try:
            while True:
                item = self.saida.get()
                if item is FECHAR:
                    break
                if item is FINALIZAR:
                    self._ws.send(json.dumps({"type": "Finalize"}))
                else:
                    self._ws.send(item)
        except Exception as erro:
            self.erro = f"envio: {type(erro).__name__}"
            self.finalizado.set()
        finally:
            try:
                self._ws.send(json.dumps({"type": "CloseStream"}))
                self._ws.close()
            except Exception:
                log.debug("fechamento do Deepgram falhou", exc_info=True)

    def _receber(self) -> None:
        try:
            for mensagem in self._ws:
                if isinstance(mensagem, bytes):
                    continue
                dados = json.loads(mensagem)
                if dados.get("type") != "Results":
                    continue
                alternativas = (dados.get("channel") or {}).get("alternatives") or [{}]
                texto = str(alternativas[0].get("transcript", "")).strip()
                if dados.get("is_final"):
                    if texto:
                        self.finais.append(texto)
                    self.parcial = ""
                    if dados.get("from_finalize"):
                        self.finalizado.set()
                else:
                    self.parcial = texto
        except Exception as erro:
            if not self.finalizado.is_set():
                self.erro = f"recepção: {type(erro).__name__}"
        finally:
            self.finalizado.set()


class Deepgram:
    """Fábrica de escutas; sem chave, `disponivel` é falso e a voz fica desligada."""

    def __init__(self, arquivo_chave: Path) -> None:
        self.arquivo_chave = arquivo_chave
        self.chave = ler_chave(arquivo_chave)
        self.segundos_hoje = (time.strftime("%Y-%m-%d"), 0.0)
        if self.chave is None:
            log.warning("Deepgram sem chave em %s: voz desligada", arquivo_chave)

    def recarregar(self) -> None:
        """O painel guardou ou apagou a chave: vale no próximo pedido, sem reiniciar o Zé."""
        self.chave = ler_chave(self.arquivo_chave)
        log.info(
            "Deepgram %s", "com chave: escuta ligada" if self.chave else "sem chave: voz desligada"
        )

    def situacao(self) -> dict[str, Any]:
        """O que a tela pode saber: se há chave e os quatro últimos caracteres."""
        return {"tem": self.chave is not None, "fim": (self.chave or "")[-4:]}

    @property
    def disponivel(self) -> bool:
        return self.chave is not None

    def nova(self) -> EscutaDeepgram:
        assert self.chave is not None  # noqa: S101 (só chamado com disponivel)
        return EscutaDeepgram(self.chave)

    def contar(self, escuta: EscutaDeepgram) -> None:
        dia, total = self.segundos_hoje
        hoje = time.strftime("%Y-%m-%d")
        total = (total if dia == hoje else 0.0) + escuta.segundos
        self.segundos_hoje = (hoje, total)
