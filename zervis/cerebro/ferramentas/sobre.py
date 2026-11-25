"""A ferramenta do Zé sobre ele mesmo (ADR 0043): "qual modelo você está usando?", "como ligo o
Live?". O retrato vem do núcleo na hora da pergunta (`zervis/nucleo/autoconhecimento.py`), sem
segredo nenhum; só lê, então passa sem perguntar."""

from collections.abc import Callable
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool


def ferramentas(sobre: Callable[[], str] | None) -> list[SdkMcpTool[Any]]:
    if sobre is None:
        return []

    @tool(
        "ze_sobre",
        "O Zé por ele mesmo: como está configurado agora (o modelo que responde, cérebro e "
        "respostas rápidas, a voz, a escuta, o Live, o modo de fala, o acesso pelo celular, as "
        "contas e a versão), o que sabe fazer (as ferramentas por área, as skills, os conectores, "
        "as sessões, as automações e a memória), o que fez nos últimos dias (pedidos, ações, "
        "falhas, o mais executado), o que espera o usuário agora (aprovações, leads, sessões "
        "paradas, revisões: o 'Precisa de você' do Início) e onde mudar cada coisa. Use sempre "
        "que o usuário perguntar o que precisa dele, ou "
        "sobre você mesmo, o que você faz ou como usar ou configurar o Zé; responda com o que vier "
        "aqui, nunca de memória.",
        {"type": "object", "properties": {}},
    )
    async def ze_sobre(args: dict[str, Any]) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": sobre()}]}

    return [ze_sobre]
