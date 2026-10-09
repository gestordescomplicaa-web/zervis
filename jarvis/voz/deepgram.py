"""Escuta em streaming pelo Deepgram nova-3 (ADR 0012; o mesmo do LIGATIA).

O áudio vai sendo transcrito enquanto o usuário fala; quando o segmentador fecha o pedido, um
`Finalize` devolve o resto em frações de segundo, em vez dos ~2 s do Whisper depois do fim.

Privacidade: uma conexão por pedido, aberta só depois do "Hey Orca" (ou na conversa contínua e na
resposta de uma confirmação) e fechada no fim do pedido; o "Hey Orca" nunca sai da máquina. A
chave vem só do arquivo `~/.config/zervis/deepgram.key` (600) e não vai para log.
"""

import json
import logging
import queue
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

log = logging.getLogger(__name__)
ENDERECO = "wss://api.deepgram.com/v1/listen"
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
FINALIZAR = object()
FECHAR = object()


class EscutaErro(RuntimeError):
    pass


def ler_chave(arquivo: Path) -> str | None:
    try:
        chave = arquivo.read_text().strip()
    except OSError:
        return None
    return chave or None


def _conectar_websocket(url: str, chave: str) -> Any:
    from websockets.sync.client import connect

    return connect(
        url, additional_headers={"Authorization": f"Token {chave}"}, open_timeout=5, close_timeout=2
    )


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
        try:
            self._ws = self.conectar(f"{ENDERECO}?{urlencode(PARAMETROS)}", self.chave)
        except Exception as erro:
            self.erro = f"conexão: {type(erro).__name__}"
            self.finalizado.set()
            return
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
        self.chave = ler_chave(arquivo_chave)
        self.segundos_hoje = (time.strftime("%Y-%m-%d"), 0.0)
        if self.chave is None:
            log.warning("Deepgram sem chave em %s: voz desligada", arquivo_chave)

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
