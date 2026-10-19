"""Os conectores do Zé nas sessões de código, por projeto (ADR 0037): o sistema de um cliente só
nos projetos dele, e os segredos nunca na linha de comando dos agentes."""

import json
import stat
import tomllib
from pathlib import Path

import pytest

from jarvis.cerebro import conectores, mcp_externo
from jarvis.cerebro.mcp_externo import McpInvalido
from jarvis.oficina.sessoes import (
    Sessao,
    arquivo_de_conectores,
    comando_terminal,
    conectores_codex,
    pede_aprovacao,
)


@pytest.fixture
def arquivos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    monkeypatch.setattr(mcp_externo, "SEGREDOS", tmp_path / "chaves" / "mcp")
    toml, painel = tmp_path / "mcp.toml", tmp_path / "mcp-painel.json"
    for nome, dados in (
        (
            "erp-loja",
            {
                "comando": "npx",
                "argumentos": ["-y", "erp-mcp"],
                "ambiente": ["ERP_TOKEN"],
                "livres": ["listar_pedidos"],
                "bloqueadas": ["apagar_pedido"],
                "projetos": ["loja"],
            },
        ),
        (
            "docs",
            {
                "tipo": "http",
                "url": "https://mcp.docs.com/v1",
                "cabecalhos": {"Authorization": "DOCS_AUTH"},
                "livres": ["buscar"],
                "projetos": ["*"],
            },
        ),
        ("pessoal", {"comando": "agenda-mcp", "livres": ["ver"]}),
    ):
        conectores.salvar(nome, dados, painel, toml)
    conectores.gravar_segredo("erp-loja", "ERP_TOKEN", "erp-segredo-123")
    conectores.gravar_segredo("docs", "DOCS_AUTH", "Bearer docs-segredo-456")
    return toml, painel


def test_cada_projeto_recebe_so_os_conectores_dele(arquivos: tuple[Path, Path]) -> None:
    toml, painel = arquivos
    loja = mcp_externo.para_projeto(Path("/clientes/loja"), toml, painel, env={})
    assert set(loja.servidores) == {"erp-loja", "docs"}
    assert loja.livres == ["mcp__erp-loja__listar_pedidos", "mcp__docs__buscar"]
    assert loja.bloqueadas == ["mcp__erp-loja__apagar_pedido"]
    outro = mcp_externo.para_projeto(Path("/clientes/padaria"), toml, painel, env={})
    assert set(outro.servidores) == {"docs"} and outro.bloqueadas == []
    # Sem `projetos`, o conector fica só na conversa com o Zé.
    assert "pessoal" in mcp_externo.carregar(toml, env={}, painel=painel).servidores


def test_projeto_e_nome_de_pasta(arquivos: tuple[Path, Path]) -> None:
    toml, painel = arquivos
    with pytest.raises(McpInvalido, match="projeto"):
        conectores.salvar("x", {"comando": "y", "projetos": ["/home/a/loja"]}, painel, toml)
    conectores.salvar("x", {"comando": "y", "projetos": ["loja", " loja ", ""]}, painel, toml)
    (listado,) = [c for c in conectores.listar(toml, painel, env={}) if c["nome"] == "x"]
    assert listado["projetos"] == ["loja"]


def test_claude_le_os_conectores_de_um_arquivo_0600(
    arquivos: tuple[Path, Path], tmp_path: Path
) -> None:
    toml, painel = arquivos
    externos = mcp_externo.para_projeto(Path("/clientes/loja"), toml, painel, env={})
    arquivo = arquivo_de_conectores(tmp_path / "sessao" / "conectores.json", externos)
    assert arquivo is not None and stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    servidores = json.loads(arquivo.read_text())["mcpServers"]
    assert servidores["erp-loja"]["env"] == {"ERP_TOKEN": "erp-segredo-123"}
    s = Sessao(id="abcd1234", nome="Loja", pasta="/clientes/loja")
    cmd = comando_terminal(s, "oi", tmp_path / "eventos", None, externos, arquivo)
    assert cmd[1:3] == ["--mcp-config", str(arquivo)]
    ajustes = json.loads(cmd[cmd.index("--settings") + 1])
    assert ajustes["permissions"] == {"allow": externos.livres, "deny": externos.bloqueadas}
    assert not any("segredo" in parte for parte in cmd)
    assert cmd[-1] == "oi"
    # Projeto sem conectores: o arquivo sai e o comando fica como antes.
    assert arquivo_de_conectores(arquivo, mcp_externo.Externos()) is None
    assert not arquivo.exists()
    assert "--mcp-config" not in comando_terminal(s, "", tmp_path / "eventos")


def test_codex_recebe_os_segredos_pelo_ambiente(arquivos: tuple[Path, Path]) -> None:
    toml, painel = arquivos
    externos = mcp_externo.para_projeto(Path("/clientes/loja"), toml, painel, env={})
    argumentos, segredos = conectores_codex(externos)
    assert not any("segredo" in a for a in argumentos)
    assert segredos == {"ERP_TOKEN": "erp-segredo-123", "ZE_MCP_DOCS_0": "Bearer docs-segredo-456"}
    config: dict[str, object] = {}
    for chave, _, valor in (a.partition("=") for a in argumentos[1::2]):
        config[chave] = tomllib.loads(f"v = {valor}")["v"]  # cada valor é TOML válido
    assert config["mcp_servers.erp-loja.env_vars"] == ["ERP_TOKEN"]
    assert config["mcp_servers.erp-loja.enabled_tools"] == ["listar_pedidos"]
    assert config["mcp_servers.docs.env_http_headers"] == {"Authorization": "ZE_MCP_DOCS_0"}
    s = Sessao(id="abcd1234", nome="Loja", pasta="/clientes/loja", motor="codex")
    cmd = comando_terminal(s, "oi", Path("/tmp/eventos"), None, externos)  # noqa: S108
    assert "mcp_servers.docs.url=" + json.dumps("https://mcp.docs.com/v1") in cmd


def test_sem_terminal_so_as_livres(arquivos: tuple[Path, Path]) -> None:
    toml, painel = arquivos
    externos = mcp_externo.para_projeto(Path("/clientes/loja"), toml, painel, env={})
    assert not pede_aprovacao("mcp__erp-loja__listar_pedidos", externos)
    assert pede_aprovacao("mcp__erp-loja__criar_pedido", externos)
    assert not pede_aprovacao("Bash", externos)
    assert not pede_aprovacao("mcp__outro__qualquer", externos)
