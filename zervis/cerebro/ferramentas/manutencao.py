"""Ferramenta do modo manutenção: o cérebro liga ou desliga quando a frase escapou do comando local.

"Coloque no modo manutenção" chegou ao cérebro em 07/10/2026 e, sem ferramenta, ele abriu o menu
de configurações. Não é de leitura: ligar manda os próximos pedidos para a sessão de código, então
passa pela aprovação falada (a frase vem do laço).
"""

import asyncio
import time
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.oficina.manutencao import Manutencao


def ferramentas(manutencao: Manutencao | None) -> list[SdkMcpTool[Any]]:
    @tool(
        "modo_manutencao",
        "Liga ou desliga o modo manutenção, ou diz como está. Ligado, os pedidos do usuário vão "
        "para a sua sessão de manutenção (um agente de código no seu próprio repositório) e "
        "você só fala o resumo do agente. "
        "Use quando ele pedir para entrar, ativar, colocar, sair ou desligar a manutenção, com "
        "qualquer palavra. Não é o menu de configurações.",
        {
            "type": "object",
            "properties": {
                "acao": {"type": "string", "enum": ["entrar", "sair", "situacao"]},
                "agente": {"type": "string", "enum": ["claude", "codex"]},
            },
            "required": ["acao"],
        },
    )
    async def modo_manutencao(args: dict[str, Any]) -> dict[str, Any]:
        if manutencao is None:
            return _erro(ValueError("modo manutenção indisponível"))
        acao = args.get("acao")
        if acao == "entrar":
            fala = await asyncio.to_thread(manutencao.entrar, str(args.get("agente") or ""))
        elif acao == "sair":
            fala = manutencao.sair()
        else:
            fala = manutencao.situacao(time.time())
        return _texto({"ligado": manutencao.ligado, "diga": fala})

    return [modo_manutencao]
