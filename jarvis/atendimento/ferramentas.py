"""As ferramentas do Zé sobre o agente de atendimento (servidor MCP "atendente", ADR 0031).

O Zé principal escreve a persona no rascunho do agente (a pasta do projeto); o caminho é de mão
única (o agente não chega ao Zé por aqui). Publicar, ligar o agente, o modo e os números de teste
ficam só na página Atendimento: decidem o que vai para clientes de verdade.
"""

import json
from pathlib import Path
from typing import Any

from claude_agent_sdk import McpSdkServerConfig, SdkMcpTool, create_sdk_mcp_server, tool

from jarvis.atendimento import agente, projeto

SERVIDOR = "atendente"
NOMES = ("atendente_ver", "atendente_definir")
LIVRES = [f"mcp__{SERVIDOR}__{n}" for n in NOMES]
CAMPOS = ("nome", "empresa", "persona", "conhecimento", "passar")


def _texto(dados: Any) -> dict[str, Any]:
    texto = dados if isinstance(dados, str) else json.dumps(dados, ensure_ascii=False)
    return {"content": [{"type": "text", "text": texto}]}


def ver(raiz: Path) -> dict[str, Any]:
    try:
        p = projeto.rascunho(raiz)
    except agente.AgenteErro as erro:
        return {"erro": str(erro)}
    return {
        "nome": p.nome,
        "empresa": p.empresa,
        "como_atender": p.persona,
        "o_que_sabe": p.conhecimento,
        "quando_passar": p.passar or agente.PASSAR_PADRAO,
        "ligado": p.ligado,
        "modo": "só números de teste" if p.modo == "teste" else "todos os contatos",
        "mudancas_sem_publicar": projeto.pendente(raiz, agente.PASTA / "publicado"),
        "pasta": str(raiz),
    }


def definir(raiz: Path, dados: dict[str, Any]) -> str:
    mudancas = {c: dados[c] for c in CAMPOS if isinstance(dados.get(c), str)}
    if not mudancas:
        return "Nada para mudar."
    try:
        projeto.gravar(raiz, mudancas)
    except (agente.AgenteErro, OSError) as erro:
        return f"Não deu: {erro}"
    return (
        "Salvo no rascunho do agente. Para valer com os clientes, publique na página Atendimento."
    )


def ferramentas(raiz: Path) -> list[SdkMcpTool[Any]]:
    @tool(
        "atendente_ver",
        "O agente que atende os clientes do usuário no WhatsApp (separado do Zé): nome, empresa, "
        "como atende, o que sabe, quando passa para o usuário, se está ligado e o modo.",
        {},
    )
    async def _ver(_: dict[str, Any]) -> dict[str, Any]:
        return _texto(ver(raiz))

    @tool(
        "atendente_definir",
        "Define a persona do agente de atendimento do WhatsApp quando o usuário pedir. Mande só "
        "os campos que mudam: nome (do agente), empresa, persona (como atender: tom, jeito, o que "
        "nunca dizer), conhecimento (serviços, preços, horários, perguntas frequentes; o texto "
        "inteiro, não só o acréscimo) e passar (quando passar a conversa para o usuário). Vai para "
        "o rascunho: publicar, ligar o agente e escolher para quem ele responde é só pela página "
        "Atendimento.",
        {
            "type": "object",
            "properties": {c: {"type": "string"} for c in CAMPOS},
        },
    )
    async def _definir(dados: dict[str, Any]) -> dict[str, Any]:
        return _texto(definir(raiz, dados))

    return [_ver, _definir]


def servidor(raiz: Path) -> McpSdkServerConfig:
    return create_sdk_mcp_server(SERVIDOR, tools=ferramentas(raiz))
