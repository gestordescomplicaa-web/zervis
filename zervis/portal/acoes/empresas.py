"""A página Empresas (ADR 0105): as empresas que quem usa gere, o grupo de WhatsApp de cada uma
e a vitrine. Nesta etapa, só o cadastro: nada é enviado nem lido nos grupos."""

from typing import Any

from zervis import atividade, empresas
from zervis.atendimento import cliente
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido


class AcoesEmpresas(Pagina):
    dependencias = ("central",)

    def empresas(self) -> dict[str, Any]:
        cadastro = empresas.PADRAO
        return {
            "empresas": [e.para_tela(cadastro.vitrine(e.id)) for e in cadastro.listar()],
            "pastas": self.painel.pastas(),
        }

    def grupos_whatsapp(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Os grupos do número do Zé (bloqueia: pergunta à Central)."""
        try:
            grupos = self.n.central.grupos()
        except cliente.CentralErro as erro:
            raise PedidoInvalido(str(erro) or "WhatsApp indisponível.") from None
        ligados = {e.grupo: e.nome for e in empresas.PADRAO.listar() if e.grupo}
        for g in grupos:
            g["empresa"] = ligados.get(str(g.get("chat", "")), "")
        return {"grupos": grupos}

    def salvar_empresa(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            empresa = empresas.PADRAO.salvar(
                str(dados.get("nome", "")),
                grupo=str(dados.get("grupo", "")),
                grupo_nome=str(dados.get("grupo_nome", "")),
                pasta=str(dados.get("pasta", ""))[:300],
                ligada=dados.get("ligada") is True,
                ident=str(dados.get("id", "")),
            )
        except empresas.EmpresaErro as erro:
            raise PedidoInvalido(str(erro)) from None
        estado = "ligada" if empresa.ligada else "desligada"
        atividade.PADRAO.registrar(
            "execucao", f"Empresa {empresa.nome} salva ({estado})", origem="painel"
        )
        return {**self.empresas(), "aviso": "Salvo."}

    def remover_empresa(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            empresa = empresas.PADRAO.remover(str(dados.get("id", "")))
        except empresas.EmpresaErro as erro:
            raise PedidoInvalido(str(erro)) from None
        atividade.PADRAO.registrar("execucao", f"Empresa {empresa.nome} removida", origem="painel")
        return {**self.empresas(), "aviso": "Removida."}
