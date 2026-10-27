"""Ferramentas do sistema: as ações do Omarchy e o estado da máquina."""

import asyncio
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.sistema import catalogo as catalogo_sistema
from zervis.sistema.estado import estado as estado_da_maquina
from zervis.sistema.politica import Sistema


def ferramentas(sistema: Sistema | None) -> list[SdkMcpTool[Any]]:
    @tool(
        "sistema_buscar",
        "Busca ações do Omarchy (o sistema desta máquina) por palavras em inglês do nome ou do "
        "resumo: volume, browser, screenshot, theme, brightness, nightlight... Devolve nome, o que "
        "faz, argumentos, exemplos e o nível de risco.",
        {"termos": str},
    )
    async def sistema_buscar(args: dict[str, Any]) -> dict[str, Any]:
        if sistema is None:
            return _erro(ValueError("sistema indisponível"))
        achadas = catalogo_sistema.buscar(sistema.acoes, args["termos"])
        return _texto(
            [
                {
                    "acao": a.nome,
                    "faz": a.resumo,
                    "argumentos": a.argumentos,
                    "exemplos": a.exemplos,
                    "risco": catalogo_sistema.NIVEIS[a.risco],
                }
                for a in achadas
            ]
            or "Nenhuma ação encontrada; tente outras palavras em inglês."
        )

    @tool(
        "sistema_estado",
        "Estado da máquina: CPU, memória disponível, swap, disco, rede, atualização, bateria, "
        "processos que mais pesam e agentes abertos há dias.",
        {},
    )
    async def sistema_estado(_: dict[str, Any]) -> dict[str, Any]:
        return _texto(await asyncio.to_thread(estado_da_maquina))

    comuns = catalogo_sistema.resumo_comuns(sistema.acoes) if sistema else ""

    @tool(
        "sistema_executar",
        "Executa uma ação do Omarchy pelo nome exato com os argumentos que ela documenta. Risco "
        "baixo roda direto; o resto pede a confirmação do usuário. As do dia a dia (execute "
        f"direto, sem buscar): {comuns}. Para outras, use sistema_buscar antes.",
        {
            "type": "object",
            "properties": {
                "acao": {"type": "string"},
                "argumentos": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["acao"],
        },
    )
    async def sistema_executar(args: dict[str, Any]) -> dict[str, Any]:
        if sistema is None:
            return _erro(ValueError("sistema indisponível"))
        try:
            return _texto(await asyncio.to_thread(sistema.executar, args))
        except ValueError as erro:
            return _erro(erro)

    return [sistema_buscar, sistema_estado, sistema_executar]
