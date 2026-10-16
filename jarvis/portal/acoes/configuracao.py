"""Ações da página configuracao."""

import asyncio
import logging
from typing import Any

from jarvis import fuso, usuario
from jarvis.cerebro import acesso, contas, logins, rapido
from jarvis.portal.acoes.pagina import Pagina
from jarvis.portal.servidor import PedidoInvalido

log = logging.getLogger(__name__)


class AcoesConfiguracao(Pagina):
    dependencias = ("aplicar_acesso", "aplicar_perfil", "cfg", "provedor", "testar_omniroute")

    def configuracao(self) -> dict[str, Any]:
        p = usuario.ler()
        return {
            "feita": usuario.existe(),
            "perfil": {"nome": p.nome, "sobre": p.sobre, "fuso": p.fuso},
            "fuso_sistema": fuso.do_sistema().key,
            "fusos": fuso.nomes(),
            "acesso": acesso.situacao(),
            "agentes": acesso.agentes(),
            "chave_anthropic": "https://console.anthropic.com/settings/keys",
            "chave_openai": "https://platform.openai.com/api-keys",
            "openai_salva": bool(rapido.ler_chave("openai", "")),  # a das Respostas rápidas
        }

    def salvar_perfil(self, dados: dict[str, Any]) -> dict[str, Any]:
        nome = str(dados.get("nome", "")).strip()
        sobre = str(dados.get("sobre", "")).strip()
        zona = str(dados.get("fuso", "")).strip()
        if len(nome) > 60:
            raise PedidoInvalido("Nome com mais de 60 caracteres.")
        if len(sobre) > 2000:
            raise PedidoInvalido("Texto com mais de 2.000 caracteres.")
        if zona and not fuso.valido(zona):
            raise PedidoInvalido("Fuso horário inválido.")
        antes = fuso.local().key
        perfil = usuario.Perfil(nome, sobre, zona)
        usuario.gravar(perfil)
        aviso = self.n.aplicar_perfil(perfil) or "Perfil salvo."
        if fuso.local().key != antes:
            aviso += " O fuso horário vale a partir do próximo início."
        return {**self.painel.configuracao(), "aviso": aviso}

    def _acesso(self, aviso: str) -> dict[str, Any]:
        return {
            "acesso": acesso.situacao(),
            "agentes": acesso.agentes(),
            "aviso": self.n.aplicar_acesso() or aviso,
        }

    def guardar_chave_claude(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            rapido.gravar_chave("anthropic", str(dados.get("chave", "")))
        except rapido.MotorErro:
            raise PedidoInvalido("Informe a chave.") from None
        return self.painel._acesso("Chave salva.")

    def guardar_chave_codex(self, dados: dict[str, Any]) -> dict[str, Any]:
        """A chave da OpenAI no Codex: colada agora ou a mesma das Respostas rápidas."""
        if dados.get("reusar"):
            chave = rapido.ler_chave("openai", "") or ""
        else:
            chave = str(dados.get("chave", ""))
        try:
            acesso.chave_no_codex(chave)
        except acesso.AcessoErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return self.painel._acesso("Chave salva no Codex.")

    def remover_acesso(self, dados: dict[str, Any]) -> dict[str, Any]:
        rapido.apagar_chave("anthropic")
        return self.painel._acesso("Chave removida.")

    def testar_acesso(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Uma pergunta mínima ao provedor escolhido com o acesso salvo."""
        if self.n.provedor == "auto":
            ok, mensagem = self.n.testar_omniroute()
            return {"ok": ok, "mensagem": mensagem}
        if self.n.provedor == "codex":
            from jarvis.cerebro.codex import testar

            ok, mensagem = asyncio.run(
                testar(self.n.cfg["cerebro"]["modelo_codex"], self.painel.pasta_teste / "codex")
            )
            return {"ok": ok, "mensagem": mensagem}
        if not acesso.situacao()["metodo"]:
            return {"ok": False, "mensagem": "Acesso não configurado."}
        modelo = self.n.cfg["cerebro"]["modelo"]
        self.painel.pasta_teste.mkdir(parents=True, exist_ok=True, mode=0o700)
        ok, mensagem = asyncio.run(acesso.testar(modelo, self.painel.pasta_teste))
        return {"ok": ok, "mensagem": mensagem}

    def contas(self) -> dict[str, Any]:
        cs = contas.Contas()
        instalados = {a["id"]: a["instalado"] for a in acesso.agentes()}
        return {
            "agentes": [
                {
                    "id": agente,
                    "nome": nome,
                    "instalado": instalados.get(agente, False),
                    "em_uso": cs.em_uso(agente).id,
                    "contas": [
                        {
                            "id": c.id,
                            "nome": c.nome,
                            "padrao": not c.pasta,
                            "comando": " ".join(c.comando_login()[1:]),
                            **contas.quem(c),
                        }
                        for c in cs.listar(agente)
                    ],
                }
                for agente, nome in contas.NOMES.items()
            ]
        }

    def adicionar_conta(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            c = contas.Contas().adicionar(str(dados.get("agente", "")), str(dados.get("nome", "")))
        except (contas.ContaErro, OSError) as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.painel.contas(), "aviso": f"Conta {c.nome} criada. Entre nela para usar."}

    def remover_conta(self, dados: dict[str, Any]) -> dict[str, Any]:
        cs = contas.Contas()
        try:
            conta = cs.achar(str(dados.get("id", "")))
            em_uso = cs.em_uso(conta.agente).id == conta.id
            cs.remover(conta.id)
        except contas.ContaErro as erro:
            raise PedidoInvalido(str(erro)) from None
        if em_uso:
            self.n.aplicar_acesso()
        return {**self.painel.contas(), "aviso": "Conta removida."}

    def usar_conta(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            conta = contas.Contas().usar(str(dados.get("id", "")))
        except contas.ContaErro as erro:
            raise PedidoInvalido(str(erro)) from None
        aviso = self.n.aplicar_acesso()
        return {**self.painel.contas(), "aviso": aviso or f"Usando a conta {conta.nome}."}

    def entrar_conta(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O login do agente roda no Zé e aparece no painel: funciona sem tela, numa VPS."""
        try:
            conta = contas.Contas().achar(str(dados.get("id", "")))
            logins.PADRAO.abrir(conta)
        except contas.ContaErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return {"login": conta.id, **logins.PADRAO.ler(conta.id, 3.0)}

    def ler_login(self, dados: dict[str, Any]) -> dict[str, Any]:
        id_ = str(dados.get("id", ""))
        estado = logins.PADRAO.ler(id_, float(dados.get("espera", 2)))
        if estado["codigo"] == 0:
            logins.PADRAO.fechar(id_)
            return {**estado, "contas": self.painel.contas(), "aviso": "Conta conectada."}
        return estado

    def codigo_login(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            logins.PADRAO.escrever(str(dados.get("id", "")), str(dados.get("codigo", "")))
        except contas.ContaErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return {}

    def fechar_login(self, dados: dict[str, Any]) -> dict[str, Any]:
        logins.PADRAO.fechar(str(dados.get("id", "")))
        return {}
