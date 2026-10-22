"""Ações da página conectores."""

import logging
from typing import Any
from urllib.parse import urlsplit

from zervis.cerebro import conectores, mcp_externo, mcp_oauth
from zervis.portal.acoes.pagina import Pagina

log = logging.getLogger(__name__)


class AcoesConectores(Pagina):
    dependencias = ("recarregar_conectores", "externos")

    def conectores(self) -> dict[str, Any]:
        return {
            "conectores": self.painel._chamar(conectores.listar),
            "pendente": self.painel.conectores_pendentes or self._mudaram(),
        }

    def _mudaram(self) -> bool:
        """Os conectores no disco diferem dos que o cérebro usa: o Zé cadastrou um pela conversa
        ou o mcp.toml mudou (o painel não viu a mudança acontecer)."""
        try:
            no_disco = mcp_externo.para_conversa(
                mcp_externo.CAMINHO, painel=mcp_externo.PAINEL, avisar=False
            )
        except mcp_externo.McpInvalido:
            return True
        return bool(no_disco != self.n.externos)

    def aplicar_conectores(self, _dados: dict[str, Any]) -> dict[str, Any]:
        aviso = self.n.recarregar_conectores()
        self.painel.conectores_pendentes = False
        return {**self.painel.conectores(), "aviso": aviso}

    def salvar_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        nome = str(dados.get("nome", "")).strip()
        self.painel._chamar(lambda: conectores.salvar(nome, dados))
        self.painel.conectores_pendentes = True
        return self.painel.conectores()

    def importar_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        """A configuração colada (JSON do MCP ou curl): salva, guarda os segredos e já testa,
        para o resultado aparecer sem outro clique. O texto colado nunca vai para o registro."""
        projetos = dados.get("projetos")
        nomes = self.painel._chamar(
            lambda: conectores.importar(
                str(dados.get("texto", "")),
                str(dados.get("nome", "")).strip(),
                [str(p) for p in projetos] if isinstance(projetos, list) else None,
                novo=bool(dados.get("novo")),
            )
        )
        self.painel.conectores_pendentes = True
        testes = [{"nome": n, **conectores.testar(n)} for n in nomes]
        return {**self.painel.conectores(), "testes": testes}

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

    def entrar_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O endereço de login do conector, para abrir no navegador (a volta é /oauth/retorno)."""
        nome = str(dados.get("nome", ""))
        url = mcp_externo.url_com_login(nome)
        if url is None:
            raise mcp_externo.McpInvalido("este conector não usa login") from None

        def iniciar() -> str:
            return mcp_oauth.PADRAO.iniciar(nome, url, str(dados.get("retorno", "")))

        return {"url": self.painel._chamar(iniciar)}

    def concluir_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O endereço em que o navegador parou, colado quando a volta não chega ao Zé."""
        consulta = urlsplit(str(dados.get("endereco", "")).strip()).query
        nome = self.painel._chamar(lambda: mcp_oauth.PADRAO.concluir(consulta))
        return {**self.painel.conectores(), "aviso": f"Conector {nome} conectado."}

    def guardar_cliente_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O app cadastrado à mão no fornecedor (servidores sem registro automático)."""
        self.painel._chamar(
            lambda: mcp_oauth.PADRAO.guardar_cliente(
                str(dados.get("nome", "")),
                str(dados.get("client_id", "")),
                str(dados.get("client_secret", "")),
            )
        )
        return self.painel.conectores()

    def apagar_cliente_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.painel._chamar(lambda: mcp_oauth.PADRAO.apagar_cliente(str(dados.get("nome", ""))))
        return self.painel.conectores()

    def sair_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.painel._chamar(lambda: mcp_oauth.PADRAO.sair(str(dados.get("nome", ""))))
        return self.painel.conectores()

    def testar_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        return dict(self.painel._chamar(lambda: conectores.testar(str(dados.get("nome", "")))))
