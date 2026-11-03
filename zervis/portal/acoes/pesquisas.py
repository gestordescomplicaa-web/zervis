"""Ações da página Pesquisas: as pesquisas que o Zé fez, guardadas com as fontes (ADR 0060)."""

from typing import Any

from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido


class AcoesPesquisas(Pagina):
    dependencias = ("pesquisas",)

    def lista_de_pesquisas(self) -> dict[str, Any]:
        return {"pesquisas": self.n.pesquisas.listar()}

    def buscar_pesquisas(self, dados: dict[str, Any]) -> dict[str, Any]:
        busca = " ".join(str(dados.get("busca", "")).split())[:200]
        return {"pesquisas": self.n.pesquisas.listar(busca)}

    def ler_pesquisa(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            pesquisa: dict[str, Any] = self.n.pesquisas.ler(str(dados.get("id", "")))
        except ValueError as erro:
            raise PedidoInvalido(str(erro)) from None
        return pesquisa

    def apagar_pesquisa(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            self.n.pesquisas.apagar(str(dados.get("id", "")))
        except ValueError as erro:
            raise PedidoInvalido(str(erro)) from None
        return self.lista_de_pesquisas()
