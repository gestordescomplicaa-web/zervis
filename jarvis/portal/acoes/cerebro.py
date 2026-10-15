"""Ações da página cerebro."""

import asyncio
import logging
from typing import Any

from jarvis.cerebro import modelos, rapido
from jarvis.portal.acoes.apoio import (
    AGENTES,
    AGENTES_SESSOES,
    MOTORES,
    catalogo_provedor,
)
from jarvis.portal.acoes.pagina import Pagina
from jarvis.portal.servidor import PedidoInvalido

log = logging.getLogger(__name__)


class AcoesCerebro(Pagina):
    dependencias = (
        "_chave_do_omniroute",
        "aplicar_via_rapida",
        "cerebro",
        "cfg",
        "configurar_omniroute",
        "modelos_do_omniroute",
        "mudar_modelo_do_cerebro",
        "persona_rapida",
        "provedor",
        "sessoes",
        "trocar_cerebro",
    )

    def _via(self) -> dict[str, Any]:
        return rapido.efetiva(self.n.cfg["via_rapida"])

    def cerebro(self) -> dict[str, Any]:
        via = self.painel._via()
        return {
            "via": {k: via[k] for k in rapido.AJUSTAVEIS},
            "ativa": isinstance(self.n.cerebro, rapido.Roteado),
            "motores": MOTORES,
            # Os motores com lista de modelos (com a versão), como no cérebro; os outros têm
            # modelos demais para listar e ficam com o campo livre.
            "listas": {
                motor: [{"id": m["id"], "nome": m["nome"]} for m in lista]
                for motor, lista in (
                    ("plano", modelos.do_cerebro("claude")),
                    ("codex", modelos.do_cerebro("codex")),
                    ("anthropic", modelos.CLAUDE),
                    ("omniroute", [{"id": r, "nome": r} for r in self.n.modelos_do_omniroute()]),
                )
            },
            "chaves": {
                m["id"]: rapido.situacao_da_chave(
                    m["id"], via["arquivo_chave"] if m["id"] == via["motor"] else ""
                )
                for m in MOTORES
            },
            "completo": self.painel._completo(),
            # Cérebro e sessões de código usam as contas cadastradas (ADR 0020).
            "agentes": AGENTES,
            "sessoes": {"agentes": AGENTES_SESSOES, "total": len(self.n.sessoes.listar())},
        }

    def _completo(self) -> dict[str, Any]:
        """O cérebro em uso para a tela: o agente, o modelo e a lista de modelos dele."""
        c, provedor = self.n.cfg["cerebro"], self.n.provedor
        omni = {
            "endereco": c["omniroute_endereco"],
            "tem_chave": bool(self.n._chave_do_omniroute()),
        }
        if provedor == "auto":
            rotas = self.n.modelos_do_omniroute()
            return {
                "provedor": "omniroute",
                "modelo": c["omniroute_rota"],
                "modelos": [{"id": r, "nome": r} for r in rotas],
                "omniroute": omni,
            }
        lista = modelos.do_cerebro(provedor) if provedor in ("claude", "codex") else []
        return {
            "provedor": provedor,
            "modelo": c["modelo_codex" if provedor == "codex" else "modelo"],
            "modelos": [{"id": m["id"], "nome": m["nome"]} for m in lista],
            "omniroute": omni,
        }

    def salvar_omniroute(self, dados: dict[str, Any]) -> dict[str, Any]:
        chave = str(dados.get("chave", "")).strip() or None  # vazio: mantém a chave salva
        try:
            aviso = self.n.configurar_omniroute(str(dados.get("endereco", "")), chave)
        except ValueError as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.painel.cerebro(), "aviso": aviso}

    def modelo_do_cerebro(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            aviso = self.n.mudar_modelo_do_cerebro(
                str(dados.get("agente", "")), str(dados.get("modelo", ""))
            )
        except ValueError as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.painel.cerebro(), "aviso": aviso}

    def escolher_cerebro(self, dados: dict[str, Any]) -> dict[str, Any]:
        agente = str(dados.get("agente", ""))
        if agente not in ("claude", "codex", "omniroute"):
            raise PedidoInvalido("Agente desconhecido.")
        aviso = self.n.trocar_cerebro(catalogo_provedor(agente))
        return {**self.painel.cerebro(), "aviso": aviso}

    def mudar_cerebro(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            rapido.gravar_escolha(dados)
        except rapido.MotorErro as erro:
            raise PedidoInvalido(str(erro)) from None
        aviso = self.n.aplicar_via_rapida()
        return {**self.painel.cerebro(), "aviso": aviso}

    def guardar_chave(self, dados: dict[str, Any]) -> dict[str, Any]:
        motor, chave = str(dados.get("motor", "")), str(dados.get("chave", ""))
        try:
            rapido.gravar_chave(motor, chave)
        except rapido.MotorErro as erro:
            raise PedidoInvalido(str(erro)) from None
        aviso = self.n.aplicar_via_rapida() if motor == self.painel._via()["motor"] else ""
        return {**self.painel.cerebro(), "aviso": aviso}

    def apagar_chave(self, dados: dict[str, Any]) -> dict[str, Any]:
        motor = str(dados.get("motor", ""))
        try:
            rapido.apagar_chave(motor)
        except rapido.MotorErro as erro:
            raise PedidoInvalido(str(erro)) from None
        aviso = self.n.aplicar_via_rapida() if motor == self.painel._via()["motor"] else ""
        return {**self.painel.cerebro(), "aviso": aviso}

    def testar(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Mede um motor com os dados da tela, ainda sem salvar."""
        try:
            escolha = rapido.validar_escolha({k: v for k, v in dados.items() if k != "ligada"})
        except rapido.MotorErro as erro:
            raise PedidoInvalido(str(erro)) from None
        via = {**self.painel._via(), **escolha}
        if via["motor"] != self.painel._via()["motor"]:
            via["arquivo_chave"] = ""
        try:
            motor = rapido.criar_motor(via, self.painel.pasta_teste)
        except rapido.MotorErro as erro:
            raise PedidoInvalido(str(erro)) from None
        if motor is None:
            return {"ok": False, "erro": "falta a chave deste motor"}
        persona = self.n.persona_rapida()
        return asyncio.run(rapido.medir(motor, persona))
