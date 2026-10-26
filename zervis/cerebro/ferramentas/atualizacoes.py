"""Ferramenta das atualizações do Zé (`zervis/versoes.py`): "tem atualização?" pela voz.

Só lê, então passa sem perguntar. Atualizar não existe aqui de propósito: o update reinicia o Zé
no meio da conversa e, no Codex, a aprovação falada não chega. Quem atualiza é a pessoa, em
Atualizações no painel.
"""

import asyncio
import time
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis import versoes
from zervis.cerebro.ferramentas.comum import _texto

VALIDADE_S = 6 * 3600  # uma procura mais velha que isso é refeita (a pergunta é "agora")


def ferramentas(fonte: versoes.Versoes | None = None) -> list[SdkMcpTool[Any]]:
    @tool(
        "atualizacoes_ver",
        "Diz se há atualização do próprio Zé (o seu código), em que canal e o que muda. Use "
        "quando o usuário perguntar se tem atualização, versão nova ou novidade do Zé. Não é a "
        "atualização do sistema (Omarchy). Você não atualiza: diga que ele atualiza em "
        "Atualizações, no painel.",
        {"type": "object", "properties": {}},
    )
    async def atualizacoes_ver(args: dict[str, Any]) -> dict[str, Any]:
        v = fonte or versoes.PADRAO
        achado = v.ultima()
        if time.time() - achado.get("procurado", 0) > VALIDADE_S:
            achado = await asyncio.to_thread(v.procurar)
        return _texto(
            {
                "disponivel": achado["disponivel"],
                "canal": achado["canal"],
                "instalada": achado["instalada"],
                "diga": achado["texto"],
                "novidades": achado["novidades"][:5],
                "onde": "Atualizações, no painel",
            }
        )

    return [atualizacoes_ver]
