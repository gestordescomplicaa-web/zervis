"""Aprovações que esperam quem usa no painel (ADR 0104).

Um pedido que chega pelo WhatsApp não se aprova por lá: quem tem o celular na mão não é,
necessariamente, quem usa. A ação que pede o "sim" espera aqui até alguém decidir no painel, que
exige login, ou até o prazo passar (aí é negada). Tudo fica em memória: um reinício nega o que
estava esperando, porque o cérebro que pediu também acabou.
"""

import asyncio
import logging
import secrets
import threading
from concurrent.futures import Future, InvalidStateError
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from zervis import fuso

log = logging.getLogger(__name__)
PRAZO_S = 600.0
MAXIMO = 20  # mais que isto esperando é um laço, não quem usa


@dataclass
class Pendente:
    id: str
    descricao: str
    origem: str
    quando: datetime
    futuro: Future[bool] = field(default_factory=Future, repr=False)

    def para_painel(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "descricao": self.descricao,
            "origem": self.origem,
            "quando": self.quando.isoformat(timespec="seconds"),
        }


class Aprovacoes:
    def __init__(self, prazo_s: float = PRAZO_S) -> None:
        self.prazo_s = prazo_s
        self._pendentes: dict[str, Pendente] = {}
        self._trava = threading.Lock()

    async def esperar(self, descricao: str, origem: str) -> bool | None:
        """Espera a decisão no painel: True aprovado, False negado, None se o prazo passou (ou
        se já há pedidos demais esperando)."""
        with self._trava:
            if len(self._pendentes) >= MAXIMO:
                log.warning("aprovações: %d esperando, pedido negado", MAXIMO)
                return None
            p = Pendente(secrets.token_hex(6), descricao, origem, datetime.now(fuso.local()))
            self._pendentes[p.id] = p
        try:
            return await asyncio.wait_for(asyncio.wrap_future(p.futuro), self.prazo_s)
        except TimeoutError:
            return None
        finally:
            with self._trava:
                self._pendentes.pop(p.id, None)

    def listar(self) -> list[dict[str, Any]]:
        with self._trava:
            return [p.para_painel() for p in self._pendentes.values()]

    def decidir(self, ident: str, aprovado: bool) -> Pendente | None:
        """A decisão do painel; None se o pedido já não espera (decidido, vencido ou outro)."""
        with self._trava:
            p = self._pendentes.pop(ident, None)
        if p is None:
            return None
        try:
            p.futuro.set_result(aprovado)
        except InvalidStateError:  # o prazo venceu no mesmo instante
            return None
        return p

    def negar_todas(self) -> None:
        with self._trava:
            pendentes, self._pendentes = list(self._pendentes.values()), {}
        for p in pendentes:
            if not p.futuro.done():
                p.futuro.set_result(False)
