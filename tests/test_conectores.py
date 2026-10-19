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


def test_acesso_negado_diz_quando_falta_o_tipo_do_token(arquivos: tuple[Path, Path]) -> None:
    """O 401 do n8n com o token sem `Bearer ` (19/10/2026): a mensagem aponta a causa, sem
    mostrar o segredo."""
    import http.server
    import threading

    class Recusa(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.send_response(401)
            self.end_headers()

        def log_message(self, *_args: object) -> None:
            pass

    servidor = http.server.HTTPServer(("127.0.0.1", 0), Recusa)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    toml, painel = arquivos
    try:
        conectores.salvar(
            "n8n",
            {
                "tipo": "http",
                "url": f"http://127.0.0.1:{servidor.server_port}/mcp-server/http",
                "cabecalhos": {"Authorization": "N8N_AUTH"},
            },
            painel,
            toml,
        )
        conectores.gravar_segredo("n8n", "N8N_AUTH", "tok-sem-tipo")
        sem_tipo = conectores.testar("n8n", toml, painel, env={})
        conectores.gravar_segredo("n8n", "N8N_AUTH", "Bearer tok-vencido")
        com_tipo = conectores.testar("n8n", toml, painel, env={})
    finally:
        servidor.shutdown()
    assert sem_tipo == {
        "ok": False,
        "erro": "Acesso negado (HTTP 401). O Authorization está sem o tipo, como Bearer.",
    }
    assert com_tipo == {"ok": False, "erro": "Acesso negado (HTTP 401). Confira o segredo."}
    assert "tok" not in str(sem_tipo) + str(com_tipo)


def test_editar_o_conector_mantem_o_segredo_guardado(arquivos: tuple[Path, Path]) -> None:
    toml, painel = arquivos
    dados = {"tipo": "http", "url": "https://a.exemplo.com/mcp", "cabecalhos": {"X": "A_AUTH"}}
    conectores.salvar("crm", dados, painel, toml)
    conectores.gravar_segredo("crm", "A_AUTH", "Bearer s3gr3d0")
    conectores.salvar("crm", {**dados, "url": "https://b.exemplo.com/mcp"}, painel, toml)
    (crm,) = [c for c in conectores.listar(toml, painel, env={}) if c["nome"] == "crm"]
    assert crm["url"] == "https://b.exemplo.com/mcp" and crm["segredos"] == {"A_AUTH": True}
