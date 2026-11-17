"""As ferramentas do cérebro sob demanda (zervis/cerebro/carga.py): a busca do Claude Code
ligada, e as mais usadas sempre à mão."""

import asyncio
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from zervis.cerebro import carga
from zervis.cerebro.claude import ClaudeBrain

AGORA = 2_000_000_000.0
DIA = 24 * 3600


def _ferramenta(nome: str) -> Any:
    @tool(nome, f"A ferramenta {nome}.", {})
    async def f(args: dict[str, Any]) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": "ok"}]}

    return f


def _listar(config: Any) -> dict[str, dict[str, Any] | None]:
    entrada = config["instance"]._request_handlers["tools/list"]
    resultado = asyncio.run(entrada.handler(None, None))
    return {f.name: f.meta for f in resultado.tools}


def test_as_mais_usadas_no_mes_e_o_padrao_completa() -> None:
    uso = {
        "mcp__jarvis__tela_agir": {"usos": 65, "ultimo": int(AGORA - DIA)},
        "mcp__jarvis__sessao_ler": {"usos": 60, "ultimo": int(AGORA - 2 * DIA)},
        "mcp__jarvis__antiga": {"usos": 500, "ultimo": int(AGORA - 60 * DIA)},  # fora do mês
        "ToolSearch": {"usos": 99, "ultimo": int(AGORA)},  # embutida: não conta
    }
    escolhidas = carga.essenciais(uso, AGORA, maximo=4, padrao=["mcp__foco__foco_ver", "x", "y"])
    assert escolhidas == {
        "mcp__jarvis__tela_agir",
        "mcp__jarvis__sessao_ler",
        "mcp__foco__foco_ver",
        "x",
    }
    assert len(carga.essenciais({}, AGORA)) == len(carga.PADRAO)  # instalação nova


def test_so_as_escolhidas_ficam_sempre_a_mao() -> None:
    config = create_sdk_mcp_server("jarvis", tools=[_ferramenta(n) for n in ("a", "b", "c")])
    outro = create_sdk_mcp_server("foco", tools=[_ferramenta("a")])
    mcp = {"jarvis": config, "foco": outro, "fora": {"type": "stdio", "command": "x"}}
    assert carga.marcar(mcp, {"mcp__jarvis__a", "mcp__jarvis__c"}) == 2
    assert _listar(config) == {"a": {carga.SEMPRE: True}, "b": None, "c": {carga.SEMPRE: True}}
    assert _listar(outro) == {"a": None}  # o nome é o do servidor certo
    # Uma sessão nova com outra escolha: troca, sem embrulhar de novo.
    carga.marcar(mcp, {"mcp__jarvis__b"})
    assert _listar(config) == {"a": None, "b": {carga.SEMPRE: True}, "c": None}


def test_o_cerebro_liga_a_busca_so_com_servidores_mcp(tmp_path: Path) -> None:
    config = create_sdk_mcp_server("jarvis", tools=[_ferramenta("a"), _ferramenta("b")])
    com = ClaudeBrain(
        "m",
        ["WebSearch", "WebFetch"],
        tmp_path,
        mcp={"jarvis": config},
        livres=["mcp__jarvis__a"],
        essenciais=lambda: {"mcp__jarvis__a"},
    )
    opcoes = com.opcoes()
    assert opcoes.tools == ["WebSearch", "WebFetch", carga.BUSCA]
    assert opcoes.allowed_tools == ["mcp__jarvis__a", carga.BUSCA]
    assert com.livres == ["mcp__jarvis__a"]  # a lista do cérebro não muda
    assert _listar(config)["a"] == {carga.SEMPRE: True}
    sem = ClaudeBrain("m", [], tmp_path)  # a via rápida: sem ferramentas, sem busca
    assert sem.opcoes().tools == [] and sem.opcoes().allowed_tools == []
