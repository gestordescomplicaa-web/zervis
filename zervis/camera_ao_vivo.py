"""O vídeo ao vivo da câmera no painel (ADR 0101): cada lente, enquanto alguém assiste.

A câmera entrega H.265 pelo RTSP, que a maioria dos navegadores não toca. O ffmpeg do sistema
converte em MJPEG (uma sequência de JPEG), que qualquer navegador mostra num `<img>`. Cada
pessoa assistindo tem o seu ffmpeg, e ele termina quando ela sai da página. A lente marcada para
girar no cadastro sai girada, como as fotos.

- "Alta": o fluxo principal, 1280x720.
- "Leve": o fluxo secundário, 640x360, para o celular e a rede de fora.
"""

import contextlib
import os
import shutil
import subprocess
import threading
from collections.abc import Callable, Iterator
from typing import Any, Protocol

from zervis import camera

FRONTEIRA = "quadro"
TIPO = f"multipart/x-mixed-replace; boundary={FRONTEIRA}"
MAXIMO = 3  # pessoas assistindo ao mesmo tempo: cada uma é um ffmpeg convertendo vídeo
PEDACO = 64 * 1024
MAXIMO_QUADRO = 4 * 1024 * 1024
QUALIDADES = {"alta": 0, "leve": 1}


class Processo(Protocol):
    """O que o vídeo usa do ffmpeg rodando (um `subprocess.Popen`)."""

    @property
    def stdout(self) -> Any: ...  # lido com read1, que o IO[bytes] do typeshed não declara

    def kill(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


Lancar = Callable[[list[str], int], Processo]


class AoVivoErro(camera.CameraErro):
    """Mensagem curta para a tela: o vídeo não pôde começar."""


def _lancar(comando: list[str], leitura: int) -> subprocess.Popen[bytes]:
    return subprocess.Popen(  # noqa: S603 - executável local fixo, argumentos estruturados.
        comando,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        pass_fds=(leitura,),
    )


def comando(ffmpeg: str, leitura: int, girar: bool) -> list[str]:
    """O ffmpeg que lê o RTSP do descritor `leitura` e escreve JPEG atrás de JPEG."""
    filtros = ["-vf", "hflip,vflip"] if girar else []
    return [
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-protocol_whitelist", camera.PROTOCOLOS_RTSP,
        "-f", "concat", "-safe", "0", "-i", f"pipe:{leitura}",
        "-an", *filtros, "-q:v", "5", "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
    ]  # fmt: skip


def quadros(fluxo: Iterator[bytes]) -> Iterator[bytes]:
    """Os JPEG inteiros de uma sequência de bytes (do início FFD8 ao fim FFD9)."""
    resto = b""
    for pedaco in fluxo:
        resto += pedaco
        while (inicio := resto.find(b"\xff\xd8")) >= 0:
            fim = resto.find(b"\xff\xd9", inicio + 2)
            if fim < 0:
                break
            yield resto[inicio : fim + 2]
            resto = resto[fim + 2 :]
        if len(resto) > MAXIMO_QUADRO:
            resto = b""


def parte(jpeg: bytes) -> bytes:
    """Um quadro no formato `multipart/x-mixed-replace`."""
    cabecalho = f"--{FRONTEIRA}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n\r\n"
    return cabecalho.encode() + jpeg + b"\r\n"


class AoVivo:
    """Quem assiste agora e o ffmpeg de cada um."""

    def __init__(
        self,
        dispositivo: camera.Camera,
        lancar: Lancar = _lancar,
        achar_ffmpeg: Callable[[], str | None] = lambda: shutil.which("ffmpeg"),
    ) -> None:
        self.dispositivo = dispositivo
        self._lancar = lancar
        self._achar_ffmpeg = achar_ffmpeg
        self._vagas = threading.BoundedSemaphore(MAXIMO)

    def transmitir(self, lente: int, qualidade: str = "alta") -> Iterator[bytes]:
        """As partes do vídeo da lente (1, 2…). Os erros saem antes da primeira parte; fechar o
        iterador (a pessoa saiu) encerra o ffmpeg."""
        conexao = self.dispositivo.conexao()
        if conexao is None:
            raise AoVivoErro("Câmera não configurada.")
        if qualidade not in QUALIDADES:
            raise AoVivoErro("Qualidade inválida.")
        if not 1 <= lente <= 16:
            raise AoVivoErro("Lente inválida.")
        ffmpeg = self._achar_ffmpeg()
        if not ffmpeg:
            raise AoVivoErro("Instale o ffmpeg para ver ao vivo.")
        if not self._vagas.acquire(blocking=False):
            raise AoVivoErro(f"Já há {MAXIMO} pessoas assistindo à câmera.")
        try:
            leitura = camera.manifesto_rtsp(conexao, lente - 1, QUALIDADES[qualidade])
            try:
                processo = self._lancar(comando(ffmpeg, leitura, lente in conexao.girar), leitura)
            finally:
                with contextlib.suppress(OSError):
                    os.close(leitura)
        except BaseException:
            self._vagas.release()
            raise
        return self._partes(processo)

    def _partes(self, processo: Processo) -> Iterator[bytes]:
        saida = processo.stdout
        try:
            if saida is None:
                return
            for jpeg in quadros(iter(lambda: saida.read1(PEDACO), b"")):
                yield parte(jpeg)
        finally:
            with contextlib.suppress(OSError):
                processo.kill()
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                processo.wait(timeout=5)
            self._vagas.release()
