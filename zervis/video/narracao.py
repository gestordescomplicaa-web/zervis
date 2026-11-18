"""A narração de um vídeo (ADR 0106) e a linha do tempo que sai dela.

Cada fala é sintetizada à parte pela voz escolhida no painel (Fish Audio, ElevenLabs ou o Cadu,
local), sem o silêncio das pontas, e começa numa batida da música: o corte da cena cai junto. Sem
voz, a duração de cada fala vem do número de palavras e o vídeo fica só com a música.
"""

import math
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

TAXA = 48000
FPS = 30
INICIO_S = 0.5  # a primeira fala entra na segunda batida
PAUSA_S = 0.35  # o respiro mínimo entre duas falas
CAUDA_S = 1.8  # o fecho segura depois da última fala
LIMIAR = 0.015  # abaixo disto, nas pontas, é silêncio
SEGUNDOS_POR_PALAVRA = 0.36  # sem voz: o ritmo de quem lê a legenda

Sintetizar = Callable[[str], tuple[int, bytes]]


@dataclass(frozen=True)
class Narracao:
    duracao: float
    falas: list[dict[str, Any]]  # {"texto", "inicio", "dur"}
    cenas: list[tuple[float, float]]  # (início, fim) de cada cena
    volume: list[float]  # da voz, por quadro, de 0 a 1
    voz: np.ndarray  # mono, 48 kHz (zeros sem voz)


def sintetizador(motor: Any) -> Sintetizar:
    """A síntese pelo motor de voz do Zé (`zervis.voz.nuvem.Motor`): PCM 16 bits mono."""
    from zervis.voz import nuvem

    def sintetizar(texto: str) -> tuple[int, bytes]:
        provedor = motor.ativo
        if provedor is None:
            taxa, fluxo = motor.local.abrir_fluxo(texto)
            return int(taxa), b"".join(iter(lambda: fluxo.read1(65536), b""))
        p = motor.provedores[provedor]
        voz = motor.escolha.voz(provedor)
        caminho, corpo, cabecalhos = p.pedido(
            texto, voz["id"], voz.get("modelo", ""), motor.chaves[provedor] or ""
        )
        if "latency" in corpo:
            corpo["latency"] = "normal"  # gravação: a qualidade vale mais que a pressa
        conexao = nuvem.conexao(p.ENDERECO, 90)
        try:
            resposta = nuvem.pedir(conexao, "POST", caminho, cabecalhos, p.motivo, corpo)
            return int(p.TAXA), resposta.read()
        finally:
            conexao.close()

    return sintetizar


def para_48k(pcm: bytes, taxa: int) -> np.ndarray:
    """O PCM em 48 kHz, sem o silêncio das pontas (fica uma margem de 30 ms)."""
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float64) / 32768
    if taxa != TAXA and len(x):
        t = np.arange(round(len(x) * TAXA / taxa)) * taxa / TAXA
        x = np.interp(t, np.arange(len(x)), x)
    forte = np.flatnonzero(np.abs(x) > LIMIAR)
    if len(forte) == 0:
        return x[:0]
    margem = int(0.03 * TAXA)
    return x[max(0, forte[0] - margem) : forte[-1] + margem]


def envelope(voz: np.ndarray, quadros: int) -> list[float]:
    passo = TAXA // FPS
    rms = [
        float(np.sqrt(np.mean(voz[i * passo : (i + 1) * passo] ** 2) + 1e-12))
        for i in range(quadros)
    ]
    altos = [r for r in rms if r > 1e-4]
    topo = float(np.percentile(altos, 95)) if altos else 1.0
    return [round(min(1.0, r / topo), 3) for r in rms]


def narrar(
    falas: list[str],
    sintetizar: Sintetizar | None,
    minimos: list[float] | None = None,
    bpm: int = 120,
) -> Narracao:
    """A voz no lugar e a linha do tempo. `minimos`: o tempo mínimo de cada cena (uma lista de
    quatro passos precisa de tempo na tela, mesmo com a fala curta)."""
    batida = 60 / bpm
    minimos = minimos or [0.0] * len(falas)
    pedacos: list[tuple[float, np.ndarray]] = []
    marcas: list[dict[str, Any]] = []
    t = INICIO_S
    for texto, minimo in zip(falas, minimos, strict=True):
        if sintetizar is not None:
            taxa, pcm = sintetizar(texto)
            x = para_48k(pcm, taxa)
        else:
            x = np.zeros(int(TAXA * (0.4 + SEGUNDOS_POR_PALAVRA * len(texto.split()))))
        inicio = math.ceil(t / batida - 1e-9) * batida
        dur = len(x) / TAXA
        pedacos.append((inicio, x))
        marcas.append({"texto": texto, "inicio": round(inicio, 3), "dur": round(dur, 3)})
        t = inicio + max(dur + PAUSA_S, minimo)
    duracao = (
        math.ceil((max(t - PAUSA_S, marcas[-1]["inicio"] + marcas[-1]["dur"]) + CAUDA_S) / batida)
        * batida
    )
    voz = np.zeros(int(duracao * TAXA))
    for inicio, x in pedacos:
        i = int(inicio * TAXA)
        voz[i : i + len(x)] += x[: max(0, len(voz) - i)]
    inicios = [0.0] + [m["inicio"] for m in marcas[1:]]
    cenas = [(a, b) for a, b in zip(inicios, [*inicios[1:], duracao], strict=True)]
    return Narracao(duracao, marcas, cenas, envelope(voz, round(duracao * FPS)), voz)


def gravar_wav(voz: np.ndarray, arquivo: Path) -> None:
    with wave.open(str(arquivo), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes((np.clip(voz, -1, 1) * 32767).astype("<i2").tobytes())
