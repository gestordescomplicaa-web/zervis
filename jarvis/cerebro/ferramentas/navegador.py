"""O navegador do JARVIS: continuar uma leitura que o filtro cortou (jarvis/cerebro/navegador.py).

As outras ferramentas do navegador são do Playwright MCP; esta é do JARVIS porque a leitura
inteira, já mascarada, fica gravada aqui, e o cérebro não lê arquivos.
"""

from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from jarvis.cerebro import navegador
from jarvis.cerebro.ferramentas.comum import _erro, _texto


def ferramentas() -> list[SdkMcpTool[Any]]:
    @tool(
        navegador.CONTINUAR,
        "Continua a leitura de uma página que o navegador cortou (o aviso de corte traz a "
        "leitura e a linha, e o índice das seções que ficaram de fora). Devolve o trecho "
        "seguinte com o mesmo teto. Use a linha da seção que interessa, não leia tudo.",
        {"leitura": str, "linha": int},
    )
    async def navegador_continuar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _texto(navegador.continuar(str(args["leitura"]), int(args["linha"])))
        except (ValueError, KeyError) as erro:
            return _erro(ValueError(str(erro)))

    return [navegador_continuar]
