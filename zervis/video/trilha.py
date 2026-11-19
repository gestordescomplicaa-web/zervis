"""A trilha de um vídeo (ADR 0106): música e efeitos compostos nota por nota, e a voz por cima.

Lá menor (Am, F, C, G), tudo na grade de batidas desde o quadro 0, no andamento do estilo. A
bateria entra no primeiro corte, o arpejo toca entre o primeiro e o último, e o último corte ganha
o acorde do fecho. Cada corte tem um "whoosh" no tom. Sob a voz, a música abaixa cerca de 10 dB.
A energia do estilo muda a mão: "calma" sem chimbal e com o bumbo leve; "alta" com chimbal em
semicolcheias. Sem amostras de ninguém: nada a licenciar.
"""

import wave
from pathlib import Path

import numpy as np

SR = 48000
ACORDES = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G (MIDI)
# As progressões que a trilha sorteia pela semente do vídeo (ADR 0113): a mesma música em todo
# vídeo era metade da sensação de "vídeo pronto".
PROGRESSOES = [
    ACORDES,
    [[48, 52, 55], [55, 59, 62], [57, 60, 64], [53, 57, 60]],  # C G Am F
    [[50, 53, 57], [46, 50, 53], [53, 57, 60], [48, 52, 55]],  # Dm Bb F C
    [[52, 55, 59], [48, 52, 55], [55, 59, 62], [50, 54, 57]],  # Em C G D
    [[53, 57, 60], [55, 59, 62], [52, 55, 59], [57, 60, 64]],  # F G Em Am
]
EFEITOS = ("whoosh", "impacto", "estalo")


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def _tempo(d: float) -> np.ndarray:
    return np.arange(int(SR * d)) / SR


def _por(buf: np.ndarray, t0: float, som: np.ndarray, g: float = 1.0) -> None:
    i = int(t0 * SR)
    j = min(len(buf), i + len(som))
    if 0 <= i < len(buf):
        buf[i:j] += g * som[: j - i]


def _passa_baixa(x: np.ndarray, corte: float) -> np.ndarray:
    a = np.exp(-2 * np.pi * corte / SR)
    y = np.empty_like(x)
    acc = 0.0
    for k, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[k] = acc
    return y


def _bumbo() -> np.ndarray:
    t = _tempo(0.35)
    f = 45 + 75 * np.exp(-t * 28)
    som: np.ndarray = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
    return som


def _chimbal(rng: np.random.Generator) -> np.ndarray:
    t = _tempo(0.05)
    som: np.ndarray = np.diff(rng.standard_normal(len(t)), prepend=0) * np.exp(-t * 90) * 0.5
    return som


def _baixo(m: int, d: float) -> np.ndarray:
    t = _tempo(d)
    s = sum(np.sin(2 * np.pi * hz(m - 24) * k * t) / k for k in range(1, 6))
    return _passa_baixa(s * np.minimum(1, t / 0.01) * np.exp(-t * 3.2), 500)


def _pad(notas: list[int], d: float) -> np.ndarray:
    t = _tempo(d)
    s = sum(np.sin(2 * np.pi * hz(m + dt) * t) for m in notas for dt in (-0.06, 0.06))
    return s * np.minimum(1, t / 0.35) * np.minimum(1, (d - t) / 0.3) / (2 * len(notas))


def _toque(m: int, d: float = 0.4) -> np.ndarray:
    t = _tempo(d)
    s = np.sin(2 * np.pi * hz(m) * t) + 0.3 * np.sin(4 * np.pi * hz(m) * t)
    som: np.ndarray = s * np.minimum(1, t / 0.004) * np.exp(-t * 9)
    return som


def _whoosh(rng: np.random.Generator, nota: int, d: float) -> np.ndarray:
    t = _tempo(d)
    r = _passa_baixa(rng.standard_normal(len(t)), 1800) + 0.25 * np.sin(2 * np.pi * hz(nota) * t)
    return r * (t / d) ** 2.2 * np.minimum(1, (d - t) / 0.02)


def _impacto(rng: np.random.Generator) -> np.ndarray:
    """O baque grave do corte seco e do carimbo."""
    t = _tempo(0.6)
    f = 32 + 60 * np.exp(-t * 18)
    grave = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6)
    ruido = _passa_baixa(rng.standard_normal(len(t)), 2500) * np.exp(-t * 35) * 0.6
    som: np.ndarray = grave + ruido
    return som


def _estalo() -> np.ndarray:
    """O clique curto da carta e da palavra que entra."""
    t = _tempo(0.07)
    som: np.ndarray = (np.sin(2 * np.pi * 1500 * t) + 0.5 * np.sin(2 * np.pi * 2900 * t)) * np.exp(
        -t * 70
    )
    return som


def compor(
    duracao: float,
    cortes: list[float],
    voz: np.ndarray | None = None,
    bpm: int = 120,
    energia: str = "media",
    semente: int = 7,
    efeitos: list[tuple[float, str]] | None = None,
) -> np.ndarray:
    """A mistura final, mono, de -1 a 1 (a voz incluída, se houver). A semente escolhe a
    progressão, o tom e o andamento; `efeitos` põe o som de cada ação na tela."""
    rng = np.random.default_rng(semente)
    progressao = PROGRESSOES[semente % len(PROGRESSOES)]
    tom = semente % 5 - 2  # de dois semitons abaixo a dois acima
    progressao = [[m + tom for m in acorde] for acorde in progressao]
    bpm = bpm + (semente % 3 - 1) * 8
    batida = 60 / bpm
    n = int(SR * duracao)
    musica, sfx = np.zeros(n), np.zeros(n)
    cortes = sorted(c for c in cortes if 0 < c < duracao) or [min(duracao / 2, 2.0)]
    primeiro, ultimo = cortes[0], cortes[-1]
    forca = {"calma": 0.45, "media": 0.9, "alta": 1.0}.get(energia, 0.9)
    for b in range(int(duracao / batida)):
        t0 = b * batida
        acorde = progressao[(b // 4) % 4]
        if b % 4 == 0:
            _por(musica, t0, _pad(acorde, 4 * batida), 0.22)
        if primeiro <= t0 < duracao - batida:
            _por(musica, t0, _bumbo(), forca if b % 2 == 0 else forca * 0.6)
            if energia != "calma":
                _por(musica, t0 + batida / 2, _chimbal(rng), 0.18)
            if energia == "alta":
                for k in (1, 3):
                    _por(musica, t0 + k * batida / 4, _chimbal(rng), 0.09)
            _por(musica, t0, _baixo(acorde[0], batida * 0.95), 0.35)
        elif t0 < primeiro and b % 2 == 0:
            _por(musica, t0, _bumbo(), 0.25)
        if primeiro <= t0 < ultimo:
            for k in range(2):
                _por(musica, t0 + k * batida / 2, _toque(acorde[(b * 2 + k) % 3] + 12), 0.1)
    _por(musica, ultimo, _pad([45, 57, 60, 64, 69], duracao - ultimo), 0.3)
    _por(musica, ultimo, _bumbo(), 1.0)
    if efeitos is None:
        for c in cortes:
            _por(sfx, c - batida, _whoosh(rng, 69, batida), 0.16)
    else:
        for quando, tipo in efeitos:
            if tipo == "impacto":
                _por(sfx, quando, _impacto(rng), 0.75)
            elif tipo == "estalo":
                _por(sfx, quando, _estalo(), 0.28)
            else:  # o whoosh termina no corte
                _por(sfx, quando - 0.32, _whoosh(rng, 69 + tom, 0.32), 0.3)
    mix = musica + sfx
    if voz is not None and len(voz):
        v = np.zeros(n)
        v[: min(n, len(voz))] = voz[:n]
        janela = int(0.02 * SR)
        nivel = np.sqrt(np.convolve(v**2, np.ones(janela) / janela, mode="same"))
        fala = _passa_baixa((nivel > 0.01).astype(np.float64), 4.0)
        mix = mix * (1 - 0.68 * np.clip(fala * 1.6, 0, 1)) + 1.35 * v
    mix *= np.minimum(1, (duracao - np.arange(n) / SR) / 0.5)
    mix = np.tanh(mix * 1.1)
    topo = float(np.max(np.abs(mix))) or 1.0
    return mix * (0.89 / topo)


def gravar(mix: np.ndarray, arquivo: Path) -> None:
    """Estéreo, 16 bits, 48 kHz."""
    with wave.open(str(arquivo), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.stack([mix, mix], axis=1) * 32767).astype("<i2").tobytes())
