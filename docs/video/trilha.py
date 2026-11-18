"""A trilha de um vídeo: música e efeitos compostos aqui, nota por nota, e a voz por cima.

Uso: trilha.py <pasta> <duração> <cortes separados por vírgula> [--voz narracao.wav]

120 BPM, Lá menor (Am, F, C, G), tudo na grade de batidas desde o quadro 0. A bateria entra no
primeiro corte, o arpejo toca entre o primeiro e o último, e o último corte ganha o acorde do
fecho. Cada corte tem um "whoosh" no tom da música. Com `--voz`, a música abaixa enquanto o Zé
fala (sem cortar a fala) e a voz entra na mistura. Sai `<pasta>/trilha.wav` (48 kHz, estéreo).
"""

import sys
import wave
from pathlib import Path

import numpy as np

SR = 48000
BATIDA = 0.5
ACORDES = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G (MIDI)
rng = np.random.default_rng(7)


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def tempo(d: float) -> np.ndarray:
    return np.arange(int(SR * d)) / SR


def por(buf: np.ndarray, t0: float, som: np.ndarray, g: float = 1.0) -> None:
    i = int(t0 * SR)
    j = min(len(buf), i + len(som))
    if 0 <= i < len(buf):
        buf[i:j] += g * som[: j - i]


def passa_baixa(x: np.ndarray, corte: float) -> np.ndarray:
    a = np.exp(-2 * np.pi * corte / SR)
    y = np.empty_like(x)
    acc = 0.0
    for k, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[k] = acc
    return y


def bumbo() -> np.ndarray:
    t = tempo(0.35)
    f = 45 + 75 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def chimbal() -> np.ndarray:
    t = tempo(0.05)
    return np.diff(rng.standard_normal(len(t)), prepend=0) * np.exp(-t * 90) * 0.5


def baixo(m: int, d: float) -> np.ndarray:
    t = tempo(d)
    s = sum(np.sin(2 * np.pi * hz(m - 24) * k * t) / k for k in range(1, 6))
    return passa_baixa(s * np.minimum(1, t / 0.01) * np.exp(-t * 3.2), 500)


def pad(notas: list[int], d: float) -> np.ndarray:
    t = tempo(d)
    s = sum(np.sin(2 * np.pi * hz(m + dt) * t) for m in notas for dt in (-0.06, 0.06))
    return s * np.minimum(1, t / 0.35) * np.minimum(1, (d - t) / 0.3) / (2 * len(notas))


def toque(m: int, d: float = 0.4) -> np.ndarray:
    t = tempo(d)
    s = np.sin(2 * np.pi * hz(m) * t) + 0.3 * np.sin(4 * np.pi * hz(m) * t)
    return s * np.minimum(1, t / 0.004) * np.exp(-t * 9)


def whoosh(nota: int) -> np.ndarray:
    d = 0.5
    t = tempo(d)
    r = passa_baixa(rng.standard_normal(len(t)), 1800) + 0.25 * np.sin(2 * np.pi * hz(nota) * t)
    return r * (t / d) ** 2.2 * np.minimum(1, (d - t) / 0.02)


def ler_mono(arquivo: Path, n: int) -> np.ndarray:
    with wave.open(str(arquivo)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768
    voz = np.zeros(n)
    voz[: min(n, len(x))] = x[:n]
    return voz


def compor(duracao: float, cortes: list[float], voz: np.ndarray | None) -> np.ndarray:
    n = int(SR * duracao)
    musica, sfx = np.zeros(n), np.zeros(n)
    primeiro, ultimo = cortes[0], cortes[-1]
    for b in range(int(duracao / BATIDA)):
        t0 = b * BATIDA
        acorde = ACORDES[(b // 4) % 4]
        if b % 4 == 0:
            por(musica, t0, pad(acorde, 4 * BATIDA), 0.22)
        if primeiro <= t0 < duracao - 0.5:
            por(musica, t0, bumbo(), 0.9 if b % 2 == 0 else 0.55)
            por(musica, t0 + BATIDA / 2, chimbal(), 0.18)
            por(musica, t0, baixo(acorde[0], BATIDA * 0.95), 0.35)
        elif t0 < primeiro and b % 2 == 0:
            por(musica, t0, bumbo(), 0.25)
        if primeiro <= t0 < ultimo:
            for k in range(2):
                por(musica, t0 + k * BATIDA / 2, toque(acorde[(b * 2 + k) % 3] + 12), 0.11)
    por(musica, ultimo, pad([45, 57, 60, 64, 69], duracao - ultimo), 0.3)
    por(musica, ultimo, bumbo(), 1.0)
    for c in cortes:
        por(sfx, c - 0.5, whoosh(69), 0.16)
    mix = musica + sfx
    if voz is not None:
        # A música abaixa (cerca de -10 dB) enquanto ele fala, com subida e descida suaves.
        janela = int(0.02 * SR)
        nivel = np.sqrt(np.convolve(voz**2, np.ones(janela) / janela, mode="same"))
        fala = passa_baixa((nivel > 0.01).astype(np.float64), 4.0)
        mix = mix * (1 - 0.68 * np.clip(fala * 1.6, 0, 1)) + 1.35 * voz
    mix *= np.minimum(1, (duracao - np.arange(n) / SR) / 0.5)
    mix = np.tanh(mix * 1.1)
    return mix * (0.89 / np.max(np.abs(mix)))


def main() -> None:
    pasta, duracao = Path(sys.argv[1]), float(sys.argv[2])
    cortes = [float(c) for c in sys.argv[3].split(",")]
    voz = None
    if "--voz" in sys.argv:
        voz = ler_mono(pasta / sys.argv[sys.argv.index("--voz") + 1], int(SR * duracao))
    mix = compor(duracao, cortes, voz)
    with wave.open(str(pasta / "trilha.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.stack([mix, mix], axis=1) * 32767).astype("<i2").tobytes())
    print(pasta / "trilha.wav")


if __name__ == "__main__":
    main()
