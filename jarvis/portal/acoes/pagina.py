"""Dependências explícitas de cada página; o painel monta o registro das ações."""

from collections.abc import Callable
from typing import Any

from jarvis.portal.acoes.contrato import ContratoPainel


class Servicos:
    def __init__(self, resolver: dict[str, Callable[[], Any]]) -> None:
        self._resolver = resolver

    def __getattr__(self, nome: str) -> Any:
        if nome not in self._resolver:
            raise AttributeError(f"Serviço não declarado pela página: {nome}")
        return self._resolver[nome]()


class Pagina:
    dependencias: tuple[str, ...] = ()

    def __init__(self, painel: ContratoPainel, servicos: Servicos) -> None:
        self.painel = painel
        self.n = servicos
