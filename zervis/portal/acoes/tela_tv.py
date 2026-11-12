"""Ações do Modo TV (ADR 0084): o cartão em Perfil (ligar, o IP da TV, achar na rede, abrir e
fechar) e mostrar na TV a peça de um projeto 3D."""

from typing import Any

from zervis import projetos3d, tv
from zervis.cerebro.ferramentas.tela_tv import mostrar_projeto
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido


class AcoesTelaTV(Pagina):
    dependencias = ("tela_tv", "projetos3d")

    def modo_tv(self) -> dict[str, Any]:
        return dict(self.n.tela_tv.para_tela())

    def salvar_modo_tv(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            self.n.tela_tv.guardar(str(dados.get("ip_tv", "")), dados.get("ligado") is True)
        except tv.TVErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.modo_tv(), "aviso": "Salvo."}

    def procurar_tv(self, dados: dict[str, Any]) -> dict[str, Any]:
        achadas = tv.descobrir()
        return {"achadas": achadas, "aviso": "" if achadas else "Nenhuma TV Samsung na rede."}

    def abrir_tv(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            self.n.tela_tv.abrir()
        except tv.TVErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.modo_tv(), "aviso": "Abrindo na TV."}

    def fechar_tv(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.n.tela_tv.fechar()
        return {**self.modo_tv(), "aviso": "Fechado."}

    def mostrar_projeto_na_tv(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            mostrar_projeto(
                self.n.tela_tv,
                self.n.projetos3d,
                str(dados.get("id", "")),
                str(dados.get("arquivo") or ""),
            )
        except (tv.TVErro, projetos3d.Projeto3DErro) as erro:
            raise PedidoInvalido(str(erro)) from None
        return {"aviso": "Na TV."}
