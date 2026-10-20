"""Ações da página melhorias."""

import logging
from typing import Any

from zervis import atividade
from zervis.portal.acoes.apoio import DIAGNOSTICO, linhas_do_registro
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido

log = logging.getLogger(__name__)


class AcoesMelhorias(Pagina):
    dependencias = (
        "aplicar_melhorias",
        "diagnosticar",
        "manutencao",
        "mudar_manutencao",
        "recomecar_diagnostico",
    )

    def melhorias(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O que a sessão de melhorias do Zé tem pronto para aprovar (ADR 0026)."""
        return dict(self.n.manutencao.mudancas())

    def sessao_de_melhorias(self, dados: dict[str, Any]) -> dict[str, Any]:
        return {"id": self.painel._chamar(lambda: self.n.manutencao.abrir_sessao())}

    def central_de_melhorias(self, dados: dict[str, Any]) -> dict[str, Any]:
        m = self.n.manutencao
        situacao = dict(m.central.situacao(m.estado.sessao))
        for candidata in situacao["candidatas"]:
            candidata["conta_nome"] = self.painel._nome_da_conta(candidata["conta"])
        return situacao

    def unificar_melhorias(self, dados: dict[str, Any]) -> dict[str, Any]:
        if dados.get("confirmado") is not True:
            atividade.PADRAO.registrar(
                "negada",
                "Unificação das sessões sem confirmação",
                origem="painel",
            )
            raise PedidoInvalido("Confirme a unificação das sessões.")
        atividade.PADRAO.origem = "painel"
        try:
            aviso = self.painel._chamar(
                lambda: self.n.manutencao.unificar_sessoes(str(dados.get("sessao", "")))
            )
        except PedidoInvalido:
            atividade.PADRAO.registrar(
                "negada",
                "Unificação das sessões indisponível",
                origem="painel",
            )
            raise
        return {"aviso": aviso}

    def aplicar_melhorias(self, dados: dict[str, Any]) -> dict[str, Any]:
        atividade.PADRAO.origem = "painel"
        return {"aviso": self.n.aplicar_melhorias(revisado=bool(dados.get("revisei")))}

    def manutencao(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Entra ou sai do estado de manutenção (ADR 0028)."""
        atividade.PADRAO.origem = "painel"
        return {"aviso": self.n.mudar_manutencao(bool(dados.get("ligar")))}

    def descartar_melhorias(self, dados: dict[str, Any]) -> dict[str, Any]:
        atividade.PADRAO.origem = "painel"
        aviso = self.n.manutencao.descartar()
        return {**self.n.manutencao.mudancas(), "aviso": aviso}

    def diagnosticar(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O relatório do que deu errado vai para a sessão de melhorias (ADR 0025 e 0026)."""
        relatorio, aviso = self.n.diagnosticar(linhas_do_registro() or [])
        return {"relatorio": relatorio, "aviso": aviso}

    def recomecar_diagnostico(self, dados: dict[str, Any]) -> dict[str, Any]:
        atividade.PADRAO.origem = "painel"
        return {"aviso": self.n.recomecar_diagnostico()}

    def diagnostico(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            return {"relatorio": DIAGNOSTICO.read_text()}
        except OSError:
            return {"relatorio": ""}
