"""O vídeo ao vivo da câmera no painel (ADR 0101): cada lente, enquanto alguém assiste.

O vídeo de cada lente vem pelo DVRIP (`OPMonitor`), o mesmo caminho do app iCSee: nesta câmera, o
RTSP traz só a lente 1, qualquer que seja o canal pedido. Ele chega em H.265, que a maioria dos
navegadores não toca; o ffmpeg do sistema recebe o H.265 pela entrada e devolve MJPEG (uma
sequência de JPEG), que qualquer navegador mostra num `<img>`. A senha não passa pelo ffmpeg.
Cada vídeo aberto tem a sua conexão e o seu ffmpeg, que terminam quando a pessoa sai da página.
A lente marcada para girar no cadastro sai girada, como as fotos.

- "Alta": o fluxo principal, 1280x720.
- "Leve": o fluxo secundário, 640x360, para o celular e a rede de fora.
"""

import contextlib
import shutil
import subprocess
import threading
from collections.abc import Callable, Iterator
from typing import Any, Protocol

from zervis import camera

FRONTEIRA = "quadro"
TIPO = f"multipart/x-mixed-replace; boundary={FRONTEIRA}"
MAXIMO = 6  # vídeos abertos ao mesmo tempo (as 3 lentes em dois aparelhos): conexão e ffmpeg
PEDACO = 64 * 1024
MAXIMO_QUADRO = 4 * 1024 * 1024
QUALIDADES = ("alta", "leve")


class Processo(Protocol):
    """O que o vídeo usa do ffmpeg rodando (um `subprocess.Popen`)."""

    @property
    def stdin(self) -> Any: ...

    @property
    def stdout(self) -> Any: ...  # lido com read1, que o IO[bytes] do typeshed não declara

    def kill(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


Lancar = Callable[[list[str]], Processo]


class AoVivoErro(camera.CameraErro):
    """Mensagem curta para a tela: o vídeo não pôde começar."""


def _lancar(comando: list[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(  # noqa: S603 - executável local fixo, argumentos estruturados.
        comando, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )


def comando(ffmpeg: str, girar: bool) -> list[str]:
    """O ffmpeg que lê H.265 da entrada e escreve JPEG atrás de JPEG."""
    filtros = ["-vf", "hflip,vflip"] if girar else []
    return [
        ffmpeg, "-hide_banner", "-loglevel", "error",
        # Sem análise longa do começo: o primeiro quadro sai com o primeiro quadro-chave.
        "-fflags", "nobuffer", "-flags", "low_delay", "-probesize", "32", "-analyzeduration", "0",
        "-f", "hevc", "-i", "pipe:0",
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


def _entregar(video: camera.Video, entrada: Any) -> None:
    """Da câmera ao ffmpeg, até um dos dois fechar."""
    with contextlib.suppress(OSError, ValueError, camera.CameraErro):
        for bloco in video:
            entrada.write(bloco)
            entrada.flush()
    with contextlib.suppress(OSError, ValueError):
        entrada.close()


class AoVivo:
    """Quem assiste agora, com a conexão e o ffmpeg de cada um."""

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
        iterador (a pessoa saiu) encerra a conexão e o ffmpeg."""
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
            raise AoVivoErro(f"Já há {MAXIMO} vídeos da câmera abertos.")
        try:
            try:
                video = self.dispositivo.video(lente - 1, principal=qualidade == "alta")
            except camera.CameraErro as erro:
                raise AoVivoErro(str(erro)) from None
            try:
                processo = self._lancar(comando(ffmpeg, lente in conexao.girar))
            except BaseException:
                video.fechar()
                raise
        except BaseException:
            self._vagas.release()
            raise
        entrega = threading.Thread(
            target=_entregar, args=(video, processo.stdin), name="camera-ao-vivo", daemon=True
        )
        entrega.start()
        return self._partes(processo, video, entrega)

    def _partes(
        self, processo: Processo, video: camera.Video, entrega: threading.Thread
    ) -> Iterator[bytes]:
        saida = processo.stdout
        try:
            if saida is None:
                return
            for jpeg in quadros(iter(lambda: saida.read1(PEDACO), b"")):
                yield parte(jpeg)
        finally:
            video.fechar()  # a leitura da câmera para, e a entrega termina com ela
            with contextlib.suppress(OSError):
                processo.kill()
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                processo.wait(timeout=5)
            entrega.join(timeout=5)
            self._vagas.release()
