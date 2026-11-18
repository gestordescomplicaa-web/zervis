"""A trilha de um vídeo de `docs/video`: música, efeitos e, com `--voz`, a narração por cima.

Uso: trilha.py <pasta> <duração> <cortes separados por vírgula> [--voz narracao.wav]

Usa `zervis.video.trilha` (o mesmo da função de Marketing). Sai `<pasta>/trilha.wav`.
"""

import sys
import wave
from pathlib import Path

import numpy as np

from zervis.video import trilha


def ler_mono(arquivo: Path) -> np.ndarray:
    with wave.open(str(arquivo)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768


def main() -> None:
    pasta, duracao = Path(sys.argv[1]), float(sys.argv[2])
    cortes = [float(c) for c in sys.argv[3].split(",")]
    voz = ler_mono(pasta / sys.argv[sys.argv.index("--voz") + 1]) if "--voz" in sys.argv else None
    trilha.gravar(trilha.compor(duracao, cortes, voz), pasta / "trilha.wav")
    print(pasta / "trilha.wav")


if __name__ == "__main__":
    main()
