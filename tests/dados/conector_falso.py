"""Um conector MCP de mentira para os testes da ponte: o segredo chega só a ele."""

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

servidor = MCPServer("falso")


@servidor.tool()
def segredo_chegou() -> str:
    """Diz se o segredo chegou ao conector (sem dizer qual é)."""
    return "sim" if os.environ.get("FALSO_TOKEN") == "segredo-do-conector" else "não"


@servidor.tool()
def onde() -> str:
    """A pasta em que o conector roda."""
    return str(Path.cwd())


@servidor.tool()
def apagar_tudo() -> str:
    """Uma ferramenta perigosa, bloqueada na configuração."""
    return "apaguei"


if __name__ == "__main__":
    servidor.run("stdio")
