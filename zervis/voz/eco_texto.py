"""O eco pelo texto (ADR 0062): a última rede contra o Zé ouvir a si mesmo.

O cancelamento de eco (o do celular, no modo de ligação, e o do servidor, ADR 0051) tira quase
tudo; o que escapa (o volume no máximo, uma caixa de som que distorce) volta transcrito como um
pedido com as palavras que o Zé acabou de dizer. Aqui, a transcrição que repete um trecho seguido
de uma fala recente do Zé (5 palavras ou mais, quase a frase inteira) é descartada.

Repetir 1 a 4 palavras do Zé ("detalha os concorrentes", "sim, envia") continua valendo: só um
trecho longo e quase igual é eco.
"""

import collections
import re
import time
import unicodedata
from collections.abc import Callable

JANELA_S = 20.0  # quanto tempo depois de mandada para tocar uma fala ainda pode voltar
SEGUIDAS = 5  # o trecho igual mais curto que conta como eco
PARTE = 0.8  # quanto da transcrição o trecho igual tem que cobrir


def palavras(texto: str) -> list[str]:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )
    return re.findall(r"\w+", sem_acento)


def _maior_trecho(a: list[str], b: list[str]) -> int:
    """O maior trecho de palavras seguidas igual nas duas listas."""
    maior = 0
    anterior = [0] * (len(b) + 1)
    for x in a:
        atual = [0] * (len(b) + 1)
        for j, y in enumerate(b, start=1):
            if x == y:
                atual[j] = anterior[j - 1] + 1
                maior = max(maior, atual[j])
        anterior = atual
    return maior


class EcoDeTexto:
    def __init__(self, agora: Callable[[], float] = time.monotonic) -> None:
        self.agora = agora
        self._falas: collections.deque[tuple[float, list[str]]] = collections.deque(maxlen=12)

    def falou(self, texto: str) -> None:
        if ditas := palavras(texto):
            self._falas.append((self.agora(), ditas))

    def eco(self, ouvido: str) -> bool:
        ouvidas = palavras(ouvido)
        if len(ouvidas) < SEGUIDAS:
            return False
        limite = self.agora() - JANELA_S
        # As frases recentes em sequência: o eco pode pegar o fim de uma e o começo da outra.
        ditas = [p for quando, frase in self._falas if quando >= limite for p in frase]
        trecho = _maior_trecho(ouvidas, ditas)
        return trecho >= SEGUIDAS and trecho >= PARTE * len(ouvidas)
