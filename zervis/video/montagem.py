"""O MP4 de um vídeo (ADR 0106): os quadros e a trilha no FFmpeg da máquina.

H.264 (yuv420p) e AAC, com o `moov` no começo (toca enquanto baixa), como o Instagram pede para
Reels. A capa (um quadro já assentado) vira também o quadro 0: as redes usam o primeiro quadro de
miniatura. Trocar o quadro 0, e não somar um, mantém a duração e o som no lugar.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

FPS = 30


class MontagemErro(RuntimeError):
    """O FFmpeg falhou ou falta; a mensagem vai para a tela."""


def ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def montar(quadros: list[Path], trilha: Path, saida: Path, capa: int) -> Path:
    """`saida` (.mp4) e, ao lado, a capa em JPEG (`capa.jpg`)."""
    binario = ffmpeg()
    if binario is None:
        raise MontagemErro("FFmpeg não encontrado nesta máquina.")
    if not quadros:
        raise MontagemErro("Nenhum quadro para montar.")
    capa = max(0, min(capa, len(quadros) - 1))
    shutil.copyfile(quadros[capa], saida.with_name("capa.jpg"))
    with tempfile.TemporaryDirectory(prefix="ze-montagem-") as tmp:
        for i, q in enumerate(quadros):
            (Path(tmp) / f"{i:04d}.jpg").symlink_to((quadros[capa] if i == 0 else q).resolve())
        feito = subprocess.run(  # noqa: S603 (o FFmpeg da máquina, com caminhos montados aqui)
            [
                binario, "-loglevel", "error", "-y", "-framerate", str(FPS),
                "-i", f"{tmp}/%04d.jpg", "-i", str(trilha),
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                "-profile:v", "high", "-movflags", "+faststart",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", str(saida),
            ],
            capture_output=True, text=True, timeout=600, check=False,
        )  # fmt: skip
    if feito.returncode != 0 or not saida.is_file():
        raise MontagemErro(f"O FFmpeg falhou: {(feito.stderr or '').strip()[:200]}")
    return saida
