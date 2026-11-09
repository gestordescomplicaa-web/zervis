"""A fala da ligação: o texto do modelo pronto para a voz (números, reais, unidades, o
raciocínio que não se fala), a voz em PCM de 16 kHz, as frases prontas para falar e o tocador
que manda a voz no ritmo da fala. Tirado de `ligacao.py`, que continua exportando os nomes."""

import asyncio
import re
import time
from collections.abc import Callable
from typing import Any

import numpy as np

TAXA = 16000
QUADRO = 960 * 2  # 60 ms de PCM 16 kHz Int16LE: o quadro do codec do WhatsApp
QUADRO_S = 0.06
_FIM_DE_FRASE = re.compile(r"(?<=[.!?…])\s+")

# Do Ligatia (RECEBE_LIGACAO/assistente.py, `_normalizar_voz` e `_RE_META`), do mesmo autor:
# o que o modelo escreve abreviado vira o que se fala, e frase de raciocínio interno nunca vira voz.
_RE_HORA_MIN = re.compile(r"\b(\d{1,2})\s*h\s*(\d{2})\b")


_RE_HORA = re.compile(r"(?<=\d)\s*h\b")


_RE_MIN = re.compile(r"(?<=\d)\s*min\b")


_RE_SEG = re.compile(r"(?<=\d)\s*seg\b")


_RE_KG = re.compile(r"(?<=\d)\s*kg\b")


_RE_KM = re.compile(r"(?<=\d)\s*km\b")


_RE_REAIS = re.compile(r"R\$\s*([\d.]*\d)(?:,(\d{1,2}))?", re.IGNORECASE)


_RE_CIFRAO = re.compile(r"R\$\s*", re.IGNORECASE)


_RE_REAIS_DUP = re.compile(r"\breais\s+reais\b", re.IGNORECASE)


_RE_PCT = re.compile(r"(?<=\d)\s*%")


_RE_NUMERO = re.compile(r"\bn[º°]", re.IGNORECASE)


_RE_META = re.compile(
    r"(?:\b(?:devo|preciso)\s+(?:encerrar|finalizar|desligar)\s+(?:a\s+)?(?:chamada|liga\w+))"
    r"|(?:\bo\s+cliente\s+(?:j[áa]\s+)?(?:se\s+despediu|encerrou|pediu|quer|disse|falou))"
    r"|(?:\b(?:let me|i should|i will|i need to|we need to|i can help"
    r"|the user|the customer|ok so)\b)",
    re.IGNORECASE,
)


def _reais(m: "re.Match[str]") -> str:
    """R$ 1.500,00 -> '1500 reais'; R$ 50,50 -> '50 reais e 50 centavos'."""
    inteiro, centavos = m.group(1), m.group(2)
    if centavos is None and "." in inteiro:
        cabeca, _, cauda = inteiro.rpartition(".")
        if cabeca and len(cauda) == 2:
            inteiro, centavos = cabeca, cauda
    inteiro = inteiro.replace(".", "")
    try:
        n = int(inteiro)
    except ValueError:
        return f"{inteiro} reais"
    texto = f"{n} {'real' if n == 1 else 'reais'}"
    if centavos:
        c = int((centavos + "00")[:2])
        if c:
            texto += f" e {c} {'centavo' if c == 1 else 'centavos'}"
    return texto


def normalizar_voz(texto: str) -> str:
    """Abreviações que a voz leria errado: '8h30' -> '8 horas e 30', 'R$ 150' -> '150 reais'."""
    t = _RE_HORA_MIN.sub(r"\1 horas e \2", texto)
    t = _RE_HORA.sub(" horas", t)
    t = _RE_MIN.sub(" minutos", t)
    t = _RE_SEG.sub(" segundos", t)
    t = _RE_KG.sub(" quilos", t)
    t = _RE_KM.sub(" quilômetros", t)
    t = _RE_REAIS.sub(_reais, t)
    t = _RE_CIFRAO.sub("", t)
    t = _RE_REAIS_DUP.sub("reais", t)
    t = _RE_PCT.sub(" por cento", t)
    return _RE_NUMERO.sub("número", t)


def e_raciocinio(frase: str) -> bool:
    """Frase de bastidor do modelo ("devo encerrar a chamada", "o cliente já se despediu")."""
    return _RE_META.search(frase) is not None


def para_16k(audio: np.ndarray, taxa: int) -> bytes:
    """Float32 na taxa do Piper -> Int16LE a 16 kHz (interpolação linear: voz, não música)."""
    if taxa != TAXA and len(audio):
        tempo = np.arange(0, len(audio) * TAXA // taxa) * (taxa / TAXA)
        audio = np.interp(tempo, np.arange(len(audio)), audio).astype(np.float32)
    return bytes((np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes())


def frases_prontas(buffer: str) -> tuple[list[str], str]:
    """As frases completas do que o modelo já escreveu e o resto, que ainda pode crescer. A marca
    `[[...]]` nunca vai para a voz."""
    corte = buffer.find("[[")
    falavel = buffer if corte < 0 else buffer[:corte]
    partes = _FIM_DE_FRASE.split(falavel)
    if corte >= 0:
        return [p for p in partes if p.strip()], buffer[corte:]
    return [p for p in partes[:-1] if p.strip()], partes[-1]


class Tocador:
    """Manda a voz ao WaCalls no ritmo da fala; `calar` descarta o que ainda não tocou."""

    def __init__(self, enviar: Callable[[bytes], Any], quadro_s: float = QUADRO_S) -> None:
        self.enviar = enviar
        self.quadro_s = quadro_s
        self.fila: asyncio.Queue[bytes] = asyncio.Queue()
        self._tocando = False
        self._quieto = asyncio.Event()
        self._quieto.set()

    @property
    def falando(self) -> bool:
        return self._tocando or not self.fila.empty()

    def tocar(self, pcm: bytes) -> None:
        for i in range(0, len(pcm), QUADRO):
            self.fila.put_nowait(pcm[i : i + QUADRO].ljust(QUADRO, b"\0"))
        if pcm:
            self._quieto.clear()

    def empurrar(self, quadro: bytes, maximo: int) -> None:
        """Um quadro já do tamanho certo (a sua voz, na ponte), sem passar de `maximo` na fila:
        se atrasou, sai o mais velho."""
        if self.fila.qsize() >= maximo:
            self.fila.get_nowait()
        self.fila.put_nowait(quadro)
        self._quieto.clear()

    def calar(self) -> None:
        while not self.fila.empty():
            self.fila.get_nowait()
        if not self._tocando:
            self._quieto.set()

    async def terminar(self) -> None:
        await self._quieto.wait()

    async def rodar(self) -> None:
        proximo = time.monotonic()
        while True:
            quadro = await self.fila.get()
            self._tocando = True
            proximo = max(proximo, time.monotonic())
            await self.enviar(quadro)
            proximo += self.quadro_s
            await asyncio.sleep(max(0.0, proximo - time.monotonic()))
            if self.fila.empty():
                self._tocando = False
                self._quieto.set()
