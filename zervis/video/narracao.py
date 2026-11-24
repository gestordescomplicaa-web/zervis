"""A narração de um vídeo (ADR 0106 e 0107) e a linha do tempo que sai dela.

Cada fala é sintetizada à parte pela voz escolhida no painel (Fish Audio, ElevenLabs ou o Cadu,
local), sem o silêncio das pontas, e começa numa batida da música: o corte da cena cai junto. Sem
voz, a duração de cada fala vem do número de palavras e o vídeo fica só com a música.

**O tempo de cada palavra** (ADR 0107) vem da própria fala gravada: o Deepgram diz quando cada
palavra começa e termina, e `alinhar` casa o que ele ouviu com as palavras do roteiro (o que não
casa, como "13" dito "treze", fica entre as vizinhas). Sem a chave do Deepgram, o tempo é
estimado pelo tamanho das palavras.
"""

import difflib
import io
import logging
import math
import re
import unicodedata
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

TAXA = 48000
FPS = 30
INICIO_S = 0.5  # a primeira fala entra na segunda batida
PAUSA_S = 0.35  # o respiro mínimo entre duas falas
PAUSA_LONGA_S = 0.8  # a mais, depois do gancho, da conta ou da virada (roteiro.PAUSA_LONGA_S)
CAUDA_S = 1.8  # o fecho segura depois da última fala
LIMIAR = 0.015  # abaixo disto, nas pontas, é silêncio
SEGUNDOS_POR_PALAVRA = 0.36  # sem voz: o ritmo de quem lê a legenda

Sintetizar = Callable[[str], tuple[int, bytes]]
# O áudio de uma fala (WAV, 48 kHz) -> as palavras ouvidas, com início e fim em segundos.
Ouvir = Callable[[bytes], list[tuple[str, float, float]]]


@dataclass(frozen=True)
class Narracao:
    duracao: float
    # {"texto", "inicio", "dur", "palavras": [{"p", "i", "f"}]}: i e f em segundos do vídeo
    falas: list[dict[str, Any]]
    cenas: list[tuple[float, float]]  # (início, fim) de cada cena
    volume: list[float]  # da voz, por quadro, de 0 a 1
    voz: np.ndarray  # mono, 48 kHz (zeros sem voz)


CADU = "cadu"  # a voz local (Piper), sem nuvem


def sintetizador(motor: Any, locutor: str = "", modelo: str = "") -> Sintetizar:
    """A síntese pelo motor de voz do Zé (`zervis.voz.nuvem.Motor`): PCM 16 bits mono. O locutor
    do vídeo (ADR 0113): vazio é a voz da página Voz; "cadu", a voz local; outro, o id de uma voz
    do Fish Audio (com a chave e o modelo da página Voz; sem a chave, a voz da página Voz). O
    modelo, se vier, é o do Fish para este vídeo (a "Qualidade da voz"), no lugar do da página
    Voz."""
    from zervis.voz import nuvem

    def sintetizar(texto: str) -> tuple[int, bytes]:
        provedor = None if locutor == CADU else motor.ativo
        voz: dict[str, str] = {}
        if locutor and locutor != CADU and motor.chaves.get("fish"):
            provedor = "fish"
            voz = {"id": locutor, "modelo": motor.escolha.voz("fish").get("modelo", "")}
        if provedor is None:
            taxa, fluxo = motor.local.abrir_fluxo(texto)
            return int(taxa), b"".join(iter(lambda: fluxo.read1(65536), b""))
        p = motor.provedores[provedor]
        voz = voz or motor.escolha.voz(provedor)
        if modelo and provedor == "fish":
            voz = {**voz, "modelo": modelo}
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


def _base(palavra: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", palavra).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def estimar(texto: str, dur: float) -> list[tuple[str, float, float]]:
    """Sem o que foi ouvido: cada palavra leva um tempo proporcional ao tamanho dela."""
    palavras = texto.split()
    total = sum(len(p) + 1 for p in palavras) or 1
    saida, t = [], 0.0
    for p in palavras:
        d = dur * (len(p) + 1) / total
        saida.append((p, t, t + d))
        t += d
    return saida


def alinhar(
    texto: str, ouvidas: list[tuple[str, float, float]], dur: float
) -> list[tuple[str, float, float]]:
    """As palavras do roteiro com o tempo do que foi ouvido. As que casam pegam o tempo exato; as
    outras ficam distribuídas entre as vizinhas que casaram."""
    roteiro = texto.split()
    if not ouvidas:
        return estimar(texto, dur)
    a, b = [_base(p) for p in roteiro], [_base(p) for p, _, _ in ouvidas]
    tempos: list[tuple[float, float] | None] = [None] * len(roteiro)
    for bloco in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(bloco.size):
            _, ini, fim = ouvidas[bloco.b + k]
            tempos[bloco.a + k] = (ini, fim)
    i = 0
    while i < len(roteiro):
        if tempos[i] is not None:
            i += 1
            continue
        j = i
        while j < len(roteiro) and tempos[j] is None:
            j += 1
        anterior = tempos[i - 1][1] if i > 0 and tempos[i - 1] else 0.0  # type: ignore[index]
        seguinte = tempos[j][0] if j < len(roteiro) and tempos[j] else max(dur, anterior)  # type: ignore[index]
        passo = max(0.0, seguinte - anterior) / (j - i)
        for k in range(i, j):
            tempos[k] = (anterior + passo * (k - i), anterior + passo * (k - i + 1))
        i = j
    return [(p, *t) for p, t in zip(roteiro, tempos, strict=True) if t is not None]


def wav_mono(x: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return buffer.getvalue()


def narrar(
    falas: list[str],
    sintetizar: Sintetizar | None,
    minimos: list[float] | None = None,
    bpm: int = 120,
    ouvir: Ouvir | None = None,
    longas: list[bool] | None = None,
) -> Narracao:
    """A voz no lugar e a linha do tempo. `minimos`: o tempo mínimo de cada cena (uma lista de
    quatro passos precisa de tempo na tela, mesmo com a fala curta). `longas`: as falas depois
    das quais a voz respira mais (o gancho, a conta, a virada)."""
    batida = 60 / bpm
    minimos = minimos or [0.0] * len(falas)
    longas = longas or [False] * len(falas)
    pedacos: list[tuple[float, np.ndarray]] = []
    marcas: list[dict[str, Any]] = []
    t = INICIO_S
    for texto, minimo, longa in zip(falas, minimos, longas, strict=True):
        if sintetizar is not None:
            taxa, pcm = sintetizar(texto)
            x = para_48k(pcm, taxa)
        else:
            x = np.zeros(int(TAXA * (0.4 + SEGUNDOS_POR_PALAVRA * len(texto.split()))))
        inicio = math.ceil(t / batida - 1e-9) * batida
        dur = len(x) / TAXA
        ouvidas: list[tuple[str, float, float]] = []
        if ouvir is not None and sintetizar is not None and len(x):
            try:
                ouvidas = ouvir(wav_mono(x))
            except Exception as erro:  # sem o Deepgram, o tempo estimado serve
                log.warning("vídeo: o tempo das palavras ficou estimado (%s)", erro)
        palavras = [
            {"p": p, "i": round(inicio + i, 3), "f": round(inicio + f, 3)}
            for p, i, f in alinhar(texto, ouvidas, dur)
        ]
        pedacos.append((inicio, x))
        marcas.append(
            {"texto": texto, "inicio": round(inicio, 3), "dur": round(dur, 3), "palavras": palavras}
        )
        t = inicio + max(dur + PAUSA_S + (PAUSA_LONGA_S if longa else 0.0), minimo)
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
