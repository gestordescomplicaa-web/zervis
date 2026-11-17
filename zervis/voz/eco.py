"""O "Ei Zé" que é a própria voz do Zé voltando pelo microfone (17/11/2026).

Enquanto o Zé fala, o detector do chamado segue ligado (é assim que a pessoa o interrompe). Num
headset, o som do fone chega ao microfone dele: medido num Dell WH1022 na cabeça, a -32 dBFS e
140 ms depois de tocar, alto o bastante para passar do volume mínimo do chamado. A redução de
ruído não ajuda: ela tira o ruído constante e deixa a voz passar, e a do Zé é voz. O resultado
era o Zé se interromper sozinho no meio da resposta, com o bipe.

O cancelador de eco da voz remota (`zervis/transporte/eco.py`, AEC3 do WebRTC) não resolve aqui:
na mesma gravação ele tirou 1 dB (de -31 para -32 dBFS). A cadeia do microfone fecha um portão
de ruído entre as falas (o microfone vai a silêncio digital), e com isso o caminho fone-microfone
deixa de ser linear, que é o que o AEC3 modela.

Então o Zé guarda o que tocou nos últimos segundos e, quando o chamado dispara, compara o
microfone com isso, em energia por faixa de frequência a cada 20 ms (o caminho fone-microfone
muda o timbre e o volume, não o desenho da fala no tempo):

- **semelhança**: a correlação entre os dois no fim do trecho, no melhor atraso;
- **sobra**: quanto o microfone passa do que se espera ouvir (o eco, com o ganho de cada faixa
  medido onde a voz do Zé soava, ou o ruído de fundo do próprio microfone nas pausas).

Só o eco: semelhança alta e quase nada sobra. Alguém dizendo "Ei Zé" por cima: a voz nova não
está na referência e sobra bem mais. Na gravação de 17/11/2026 (19 s de fala, 62 chamados
simulados): o eco, com sobra de até 10,8 dB, barrado em 62 de 62; o chamado de verdade por cima,
com sobra de 12,1 dB ou mais, aceito em 62 de 62; com a voz 6 dB mais baixa (no limite do volume
mínimo), aceito em 59 de 62. Com chiado de -50 dBFS no microfone, o eco segue barrado em 62 de 62.
"""

import collections
import itertools
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

TAXA = 16000  # a do microfone (transporte local) e a da comparação
QUADRO = 320  # 20 ms
FAIXAS_HZ = (150, 400, 900, 1800, 3800)
ANTES_S = 1.6  # o som pode chegar ao microfone até isto depois de tocar (fone Bluetooth, buffers)
DEPOIS_S = 0.4  # e o quadro do microfone pode chegar antes do horário que a voz anotou
FIM_S = 1.2  # o chamado está no fim do trecho: é ali que se compara
SEMELHANCA_MINIMA = 0.80
SOBRA_MAXIMA_DB = 11.5
GUARDA_S = 10.0  # quanto da fala fica guardado
Amostras = NDArray[np.float32]


@dataclass(frozen=True)
class Veredito:
    eco: bool
    semelhanca: float
    sobra_db: float


def _para_16k(amostras: NDArray[np.float32], taxa: int) -> Amostras:
    if taxa == TAXA or len(amostras) == 0:
        return amostras.astype(np.float32)
    n = max(1, round(len(amostras) * TAXA / taxa))
    eixo = np.linspace(0, len(amostras) - 1, n)
    return np.interp(eixo, np.arange(len(amostras)), amostras).astype(np.float32)


def _faixas(x: NDArray[np.float64]) -> NDArray[np.float64]:
    """Energia (dB) por faixa, a cada 20 ms. O piso fixo iguala silêncio e ruído muito baixo."""
    n = len(x) // QUADRO
    quadros = x[: n * QUADRO].reshape(n, QUADRO) * np.hanning(QUADRO)
    espectro = np.abs(np.fft.rfft(quadros, axis=1)) ** 2
    freq = np.fft.rfftfreq(QUADRO, 1 / TAXA)
    faixas = [
        espectro[:, (freq >= baixo) & (freq < alto)].sum(axis=1)
        for baixo, alto in itertools.pairwise(FAIXAS_HZ)
    ]
    return np.asarray(10 * np.log10(np.stack(faixas, axis=1) + 1e3), dtype=np.float64)


def _correlacao(a: NDArray[np.float64], b: NDArray[np.float64]) -> float:
    za = (a - a.mean(axis=0)) / (a.std(axis=0) + 1e-9)
    zb = (b - b.mean(axis=0)) / (b.std(axis=0) + 1e-9)
    return float((za * zb).mean())


def julgar(microfone: bytes, referencia: Amostras) -> Veredito:
    """`microfone`: PCM s16le a 16 kHz que terminou agora. `referencia`: o que tocou, a 16 kHz e
    na escala de -1 a 1, de ANTES_S antes do começo do microfone até DEPOIS_S depois do fim."""
    m = _faixas(np.frombuffer(microfone, dtype="<i2").astype(np.float64))
    r = _faixas(referencia.astype(np.float64) * 32768)
    antes, depois, fim = (round(s * TAXA / QUADRO) for s in (ANTES_S, DEPOIS_S, FIM_S))
    if len(m) < fim or len(r) < len(m) + antes:
        return Veredito(False, 0.0, 99.0)
    melhor: tuple[float, NDArray[np.float64]] | None = None
    for atraso in range(-min(depois, len(r) - len(m) - antes), antes + 1):
        inicio = antes - atraso
        alinhada = r[inicio : inicio + len(m)]
        if len(alinhada) < len(m):
            continue
        semelhanca = _correlacao(m, alinhada)
        if melhor is None or semelhanca > melhor[0]:
            melhor = (semelhanca, alinhada)
    if melhor is None:
        return Veredito(False, 0.0, 99.0)
    alinhada = melhor[1]
    # O caminho fone-microfone, por faixa, medido onde a voz do Zé soava (não nas pausas).
    soando = alinhada > np.percentile(alinhada, 20, axis=0) + 6
    diferenca = np.where(soando, m - alinhada, np.nan)
    ganho = np.nan_to_num(np.nanmedian(diferenca, axis=0), nan=float(np.median(m - alinhada)))
    # O que se espera ouvir: o eco ou, nas pausas, o ruído de fundo do próprio microfone.
    piso = np.percentile(m, 10, axis=0) + 3
    esperado = np.maximum(alinhada + ganho, piso)
    sobra = (m - esperado)[-fim:].max(axis=1)
    semelhanca = _correlacao(m[-fim:], alinhada[-fim:])
    sobra_db = float(np.percentile(sobra, 90))
    eco = semelhanca >= SEMELHANCA_MINIMA and sobra_db < SOBRA_MAXIMA_DB
    return Veredito(eco, round(semelhanca, 3), round(sobra_db, 1))


class Referencia:
    """O que a voz do Zé tocou nos últimos segundos, no relógio monotônico."""

    def __init__(self, relogio: Callable[[], float] = time.monotonic) -> None:
        self.relogio = relogio
        self._trechos: collections.deque[tuple[float, Amostras]] = collections.deque()
        self._trava = threading.Lock()

    def tocou(self, inicio: float, amostras: NDArray[np.float32], taxa: int) -> None:
        """Amostras entregues ao reprodutor que começam a soar em `inicio`."""
        trecho = _para_16k(amostras, taxa)
        if not len(trecho):
            return
        with self._trava:
            self._trechos.append((inicio, trecho))
            limite = self.relogio() - GUARDA_S
            while self._trechos and self._trechos[0][0] + len(self._trechos[0][1]) / TAXA < limite:
                self._trechos.popleft()

    def trecho(self, inicio: float, fim: float) -> Amostras | None:
        """O que soou entre `inicio` e `fim` (silêncio onde nada tocou); None se nada tocou."""
        saida = np.zeros(max(0, round((fim - inicio) * TAXA)), dtype=np.float32)
        tocou = False
        with self._trava:
            trechos = list(self._trechos)
        for comeco, amostras in trechos:
            de = round((comeco - inicio) * TAXA)
            ate = de + len(amostras)
            if ate <= 0 or de >= len(saida):
                continue
            corte = max(0, -de)
            saida[max(0, de) : min(len(saida), ate)] = amostras[
                corte : corte + min(len(saida), ate) - max(0, de)
            ]
            tocou = True
        return saida if tocou else None

    def avaliar(self, microfone: bytes, fim: float | None = None) -> Veredito | None:
        """O chamado que terminou em `fim` (agora) é eco da própria fala? None: nada tocou."""
        fim = self.relogio() if fim is None else fim
        inicio = fim - len(microfone) / 2 / TAXA
        referencia = self.trecho(inicio - ANTES_S, fim + DEPOIS_S)
        if referencia is None or not np.any(referencia):
            return None
        return julgar(microfone, referencia)
