"""Cérebro "eco" da Fase 1: repete o pedido, para testar o ciclo inteiro sem custo."""

import asyncio
from collections.abc import AsyncIterator

from jarvis.cerebro.base import Aprovar, EventoCerebro, Fim, Texto


class Eco:
    def __init__(self, atraso_s: float = 0.05) -> None:
        self.atraso_s = atraso_s

    async def start(self, persona: str, aprovar: Aprovar | None = None) -> None:
        return None

    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        # Chega em pedaços, como um cérebro de verdade, para exercitar a fala por frase.
        for pedaco in ("Você disse: ", texto.strip().rstrip(".!?"), "."):
            await asyncio.sleep(self.atraso_s)
            yield Texto(pedaco)
        yield Fim()

    async def interrupt(self) -> None:
        return None

    async def reset(self) -> None:
        return None

    async def close(self) -> None:
        return None
