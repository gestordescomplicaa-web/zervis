"""Ações da página Projetos 3D (ADR 0082 e 0083): os projetos com os arquivos e as medidas, criar
um (a pasta e a sessão de código que modela), mostrar um modelo na Imersão, os ajustes, e a
impressora: achar na rede, guardar a conexão, ver o status, fatiar e imprimir."""

import base64
from typing import Any

from zervis import impressora3d, projetos3d
from zervis.cerebro.ferramentas.sessoes import motor_conectado
from zervis.oficina.sessoes import SessaoErro
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido
from zervis.rosto.tela import TelaErro


class AcoesProjetos3D(Pagina):
    dependencias = ("projetos3d", "sessoes", "tela", "impressora3d", "tela_tv")

    def projetos_3d(self) -> dict[str, Any]:
        return {
            "projetos": self.n.projetos3d.listar(),
            "ajustes": self.n.projetos3d.ajustes(),
            "raiz": str(self.n.projetos3d.raiz),
            "impressora": {
                **self.n.impressora3d.para_tela(),
                "avisos": [
                    {k: a[k] for k in ("quando", "fala", "texto")}
                    for a in self.n.impressora3d.avisos()[:5]
                ],
            },
            "tv": bool(self.n.tela_tv.ajustes()["ligado"]),
        }

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
                self.n.projetos3d,
                self.n.sessoes,
                str(dados.get("id", "")),
                motor_conectado(),
                "painel",
            )
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

    # ---- a impressora (ADR 0083) ----

    def guardar_impressora(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            self.n.impressora3d.guardar(
                str(dados.get("ip", "")), str(dados.get("serie", "")), str(dados.get("codigo", ""))
            )
        except impressora3d.ImpressoraErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.projetos_3d(), "aviso": "Salvo."}

    def procurar_impressora(self, dados: dict[str, Any]) -> dict[str, Any]:
        achadas = impressora3d.descobrir()
        return {"achadas": achadas, "aviso": "" if achadas else "Nenhuma impressora na rede."}

    def foto_da_impressora(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Uma foto agora da câmera da impressora (ADR 0085)."""
        if self.n.impressora3d.fotografar is None:
            raise PedidoInvalido("Câmera indisponível.")
        try:
            caminho = self.n.impressora3d.fotografar()
        except (impressora3d.ImpressoraErro, OSError):
            raise PedidoInvalido("A câmera não respondeu.") from None
        foto = base64.b64encode(caminho.read_bytes()).decode()
        return {"foto": f"data:image/jpeg;base64,{foto}"}

    def trajetos_do_projeto_3d(self, dados: dict[str, Any]) -> dict[str, Any]:
        """A prévia do fatiamento: o caminho do bico, camada por camada."""
        try:
            return projetos3d.trajetos(
                self.n.projetos3d, str(dados.get("id", "")), str(dados.get("arquivo") or "")
            )
        except projetos3d.Projeto3DErro as erro:
            raise PedidoInvalido(str(erro)) from None

    def status_da_impressora(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            return {"status": self.n.impressora3d.status()}
        except impressora3d.ImpressoraErro as erro:
            raise PedidoInvalido(str(erro)) from None

    def comando_da_impressora(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            self.n.impressora3d.comando(str(dados.get("comando", "")))
        except impressora3d.ImpressoraErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return {"aviso": "Enviado."}

    def fatiar_projeto_3d(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            fatia = projetos3d.fatiar(
                self.n.projetos3d,
                self.n.impressora3d,
                str(dados.get("id", "")),
                str(dados.get("arquivo") or ""),
            )
        except projetos3d.Projeto3DErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.projetos_3d(), "aviso": fatia["fala"]}

    def imprimir_projeto_3d(self, dados: dict[str, Any]) -> dict[str, Any]:
        if dados.get("confirmado") is not True:
            raise PedidoInvalido("Confirme a impressão.")
        try:
            feito = projetos3d.imprimir(
                self.n.projetos3d,
                self.n.impressora3d,
                str(dados.get("id", "")),
                str(dados.get("arquivo") or ""),
            )
        except projetos3d.Projeto3DErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.projetos_3d(), "aviso": "Enviado para a impressora."} | {"feito": feito}
