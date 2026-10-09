"""Conectores MCP pelo painel: junto do mcp.toml, segredos 0600, ligar/desligar e testar."""

import stat
import sys
from pathlib import Path

import pytest

from jarvis.cerebro import conectores, mcp_externo
from jarvis.cerebro.mcp_externo import McpInvalido

TOML = """
[servidores.navegador]
comando = "node"
argumentos = ["cli.js"]
livres = ["browser_navigate"]
"""

# Um servidor MCP mínimo, de verdade, falando JSON-RPC pelo stdin/stdout.
SERVIDOR = r"""
import json, sys
for linha in sys.stdin:
    msg = json.loads(linha)
    if msg.get("method") == "initialize":
        r = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
             "serverInfo": {"name": "falso", "version": "1"}}
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": r}), flush=True)
    elif msg.get("method") == "tools/list":
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": [
            {"name": "criar_issue", "description": "Cria uma issue"},
            {"name": "listar_repos", "description": "Lista os repositórios"}]}}), flush=True)
"""


@pytest.fixture
def arquivos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    toml = tmp_path / "mcp.toml"
    toml.write_text(TOML)
    monkeypatch.setattr(mcp_externo, "SEGREDOS", tmp_path / "chaves" / "mcp")
    return toml, tmp_path / "mcp-painel.json"


def test_painel_soma_ao_toml_sem_tocar_nele(arquivos: tuple[Path, Path]) -> None:
    toml, painel = arquivos
    conectores.salvar(
        "github",
        {"tipo": "stdio", "comando": "npx", "argumentos": ["-y", "srv"], "ambiente": ["GH_TOKEN"]},
        painel,
        toml,
    )
    todos = {c["nome"]: c for c in conectores.listar(toml, painel, env={})}
    assert todos["github"]["origem"] == "painel" and todos["navegador"]["origem"] == "arquivo"
    assert todos["github"]["segredos"] == {"GH_TOKEN": False}
    assert toml.read_text() == TOML
    with pytest.raises(McpInvalido, match=r"mcp\.toml"):
        conectores.salvar("navegador", {"comando": "x"}, painel, toml)
    for nome, dados in (
        ("Com Espaço", {"comando": "x"}),
        ("x", {"comando": "x", "ambiente": ["minusculo"]}),
        ("y", {"tipo": "http", "url": "http://site.com/mcp"}),
    ):
        with pytest.raises(McpInvalido):
            conectores.salvar(nome, dados, painel, toml)


def test_segredo_guardado_vale_no_carregar_e_nunca_volta(arquivos: tuple[Path, Path]) -> None:
    toml, painel = arquivos
    conectores.salvar("github", {"comando": "npx", "ambiente": ["GH_TOKEN"]}, painel, toml)
    assert "github" not in mcp_externo.carregar(toml, env={}, painel=painel).servidores
    conectores.gravar_segredo("github", "GH_TOKEN", "ghp_segredo")
    arquivo = mcp_externo.SEGREDOS / "github" / "GH_TOKEN"
    assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    carregados = mcp_externo.carregar(toml, env={}, painel=painel)
    assert carregados.servidores["github"]["env"] == {"GH_TOKEN": "ghp_segredo"}
    listado = next(c for c in conectores.listar(toml, painel, env={}) if c["nome"] == "github")
    assert listado["segredos"] == {"GH_TOKEN": True} and "ghp_segredo" not in str(listado)


def test_ligar_desligar_e_remover(arquivos: tuple[Path, Path]) -> None:
    toml, painel = arquivos
    conectores.ligar("navegador", False, painel)
    assert "navegador" not in mcp_externo.carregar(toml, env={}, painel=painel).servidores
    conectores.ligar("navegador", True, painel)
    assert "navegador" in mcp_externo.carregar(toml, env={}, painel=painel).servidores
    conectores.salvar("x", {"comando": "y"}, painel, toml)
    conectores.remover("x", painel)
    assert "x" not in {c["nome"] for c in conectores.listar(toml, painel, env={})}
    with pytest.raises(McpInvalido, match="painel"):
        conectores.remover("navegador", painel)


def test_testar_sobe_o_servidor_e_lista_as_ferramentas(
    arquivos: tuple[Path, Path], tmp_path: Path
) -> None:
    toml, painel = arquivos
    script = tmp_path / "servidor.py"
    script.write_text(SERVIDOR)
    conectores.salvar(
        "falso", {"comando": sys.executable, "argumentos": [str(script)]}, painel, toml
    )
    r = conectores.testar("falso", toml, painel, env={})
    assert r["ok"] and [f["nome"] for f in r["ferramentas"]] == ["criar_issue", "listar_repos"]
    conectores.salvar(
        "falso",
        {
            "comando": sys.executable,
            "argumentos": [str(script)],
            "livres": ["listar_repos"],
            "bloqueadas": ["criar_issue"],
        },
        painel,
        toml,
    )
    carregado = mcp_externo.carregar(toml, env={}, painel=painel)
    assert "mcp__falso__listar_repos" in carregado.livres
    assert carregado.bloqueadas == ["mcp__falso__criar_issue"]
    conectores.salvar("quebrado", {"comando": "/nao/existe"}, painel, toml)
    assert conectores.testar("quebrado", toml, painel, env={})["ok"] is False
