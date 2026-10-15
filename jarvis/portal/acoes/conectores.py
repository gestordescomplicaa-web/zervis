"""Ações da página conectores."""

import logging
from typing import Any

from jarvis.cerebro import conectores
from jarvis.portal.acoes.pagina import Pagina

log = logging.getLogger(__name__)


class AcoesConectores(Pagina):
    dependencias = ("recarregar_conectores",)

    def conectores(self) -> dict[str, Any]:
        return {
            "conectores": self.painel._chamar(conectores.listar),
            "pendente": self.painel.conectores_pendentes,
        }

    def aplicar_conectores(self, _dados: dict[str, Any]) -> dict[str, Any]:
        aviso = self.n.recarregar_conectores()
        self.painel.conectores_pendentes = False
        return {**self.painel.conectores(), "aviso": aviso}

    def salvar_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        nome = str(dados.get("nome", "")).strip()
        self.painel._chamar(lambda: conectores.salvar(nome, dados))
        self.painel.conectores_pendentes = True
        return self.painel.conectores()

    def remover_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.painel._chamar(lambda: conectores.remover(str(dados.get("nome", ""))))
        self.painel.conectores_pendentes = True
        return self.painel.conectores()

    def ligar_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.painel._chamar(
            lambda: conectores.ligar(str(dados.get("nome", "")), bool(dados.get("ligado")))
        )
        self.painel.conectores_pendentes = True
        return self.painel.conectores()

    def segredo_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.painel._chamar(
            lambda: conectores.gravar_segredo(
                str(dados.get("nome", "")),
                str(dados.get("variavel", "")),
                str(dados.get("valor", "")),
            )
        )
        self.painel.conectores_pendentes = True
        return self.painel.conectores()

    def testar_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        return dict(self.painel._chamar(lambda: conectores.testar(str(dados.get("nome", "")))))
