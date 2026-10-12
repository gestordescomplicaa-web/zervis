"""Troca de conta só antes de qualquer resposta ou ação, sem repetir pedidos concluídos."""

import asyncio
from collections.abc import AsyncIterator

import pytest

from jarvis.cerebro.base import EventoCerebro, Fim, Texto
from jarvis.cerebro.eco import Eco
from jarvis.cerebro.reserva import ComReserva


class ContaFalsa(Eco):
    def __init__(self, eventos: list[EventoCerebro], ferramentas: list[str] | None = None) -> None:
        super().__init__(atraso_s=0)
        self.eventos = eventos
        self.pedidos: list[str] = []
        self.ferramentas_usadas = ferramentas or []
        self.uso = {"input_tokens": 2}
        self.fechado = False

    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        self.pedidos.append(texto)
        for evento in self.eventos:
            yield evento

    async def close(self) -> None:
        self.fechado = True


def test_troca_por_cota_leva_contexto_e_conserva_conta_que_funciona() -> None:
    primeira = ContaFalsa([Texto("Oi."), Fim()])
    segunda = ContaFalsa([Texto("Tudo bem."), Fim()])
    brain = ComReserva(primeira, [("segunda", lambda: segunda)])

    async def rodar() -> None:
        await brain.start("persona")
        assert [e async for e in brain.ask("Olá")] == [Texto("Oi."), Fim()]
        primeira.eventos = [Fim("limite_de_uso")]
        assert [e async for e in brain.ask("Tudo bem?")] == [Texto("Tudo bem."), Fim()]
        assert "Olá" in segunda.pedidos[0] and "Oi." in segunda.pedidos[0]
        assert brain.uso is not None and brain.uso["input_tokens"] == 4
        assert primeira.fechado
        assert [e async for e in brain.ask("E agora?")] == [Texto("Tudo bem."), Fim()]
        assert len(primeira.pedidos) == 2 and segunda.pedidos[-1] == "E agora?"

    asyncio.run(rodar())


@pytest.mark.parametrize("texto,ferramentas", [("Já comecei.", []), ("", ["enviar"])])
def test_nao_repete_apos_texto_ou_ferramenta(texto: str, ferramentas: list[str]) -> None:
    eventos: list[EventoCerebro] = ([Texto(texto)] if texto else []) + [Fim("limite_de_uso")]
    primeira = ContaFalsa(eventos, ferramentas)
    segunda = ContaFalsa([Texto("Duplicado"), Fim()])
    brain = ComReserva(primeira, [("segunda", lambda: segunda)])

    async def rodar() -> None:
        assert [e async for e in brain.ask("Pedido")] == eventos
        assert segunda.pedidos == []

    asyncio.run(rodar())
