"""Ações da página Projetos 3D (ADR 0082): os projetos com os arquivos e as medidas, criar um
(a pasta e a sessão de código que modela), mostrar um modelo na Imersão e os ajustes."""

from typing import Any

from zervis import projetos3d
from zervis.cerebro.ferramentas.sessoes import motor_conectado
from zervis.oficina.sessoes import SessaoErro
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido
from zervis.rosto.tela import TelaErro


class AcoesProjetos3D(Pagina):
    dependencias = ("projetos3d", "sessoes", "tela")

    def projetos_3d(self) -> dict[str, Any]:
        return {"projetos": self.n.projetos3d.listar(), "ajustes": self.n.projetos3d.ajustes()}

    def criar_projeto_3d(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Uma peça funcional (sem imagem), pelo formulário da página."""
        return self._criar(dados, None)

    def criar_projeto_3d_com_imagem(self, corpo: bytes, consulta: dict[str, str]) -> dict[str, Any]:
        """Uma arte a partir de imagem: a imagem vem no corpo; o resto, no endereço."""
        return self._criar(dict(consulta), corpo)

    def _criar(self, dados: dict[str, Any], imagem: bytes | None) -> dict[str, Any]:
        try:
            p = self.n.projetos3d.criar(
                str(dados.get("nome", "")),
                str(dados.get("tipo", "")),
                str(dados.get("pedido", "")),
                imagem,
                str(dados.get("nome_imagem", "")),
            )
        except projetos3d.Projeto3DErro as erro:
            raise PedidoInvalido(str(erro)) from None
        try:
            projetos3d.comecar(
                self.n.projetos3d, self.n.sessoes, p["id"], motor_conectado(), "painel"
            )
        except (projetos3d.Projeto3DErro, SessaoErro) as erro:  # a pasta fica; a sessão, depois
            return {**self.projetos_3d(), "aviso": f"Projeto criado; a sessão não começou: {erro}"}
        return {**self.projetos_3d(), "aviso": "Projeto criado. A sessão começou a modelar."}

    def comecar_projeto_3d(self, dados: dict[str, Any]) -> dict[str, Any]:
        """A sessão de um projeto que ficou sem (a primeira não começou, ou foi excluída)."""
        try:
            projetos3d.comecar(
                self.n.projetos3d, self.n.sessoes, str(dados.get("id", "")), motor_conectado(),
                "painel",
            )  # fmt: skip
        except (projetos3d.Projeto3DErro, SessaoErro) as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.projetos_3d(), "aviso": "A sessão começou a modelar."}

    def mostrar_projeto_3d(self, dados: dict[str, Any]) -> dict[str, Any]:
        id_ = str(dados.get("id", ""))
        try:
            previa = self.n.projetos3d.previa(id_, str(dados.get("arquivo") or ""))
            nome = self.n.projetos3d.ler(id_)["nome"]
        except projetos3d.Projeto3DErro as erro:
            raise PedidoInvalido(str(erro)) from None
        acao = {"acao": "mostrar_modelo", "alvo": previa, "valor": nome, "estilo": "solido"}
        try:
            self.n.tela.agir([acao])
        except (TelaErro, OSError):
            raise PedidoInvalido("Abra a Imersão para ver o modelo.") from None
        return {"aviso": "Na Imersão.", "previa": previa}

    def ajustes_projetos_3d(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            self.n.projetos3d.guardar_ajustes(
                str(dados.get("impressora", "")),
                list(dados.get("mesa_mm") or []),
                str(dados.get("pipeline_arte", "")),
            )
        except projetos3d.Projeto3DErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.projetos_3d(), "aviso": "Salvo."}
