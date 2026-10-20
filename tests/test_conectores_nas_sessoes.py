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


def test_projeto_e_nome_de_pasta_ou_caminho_inteiro(arquivos: tuple[Path, Path]) -> None:
    toml, painel = arquivos
    for invalido in ("home/a/loja", "/home/a/../b", "loja*"):
        with pytest.raises(McpInvalido, match="projeto"):
            conectores.salvar("x", {"comando": "y", "projetos": [invalido]}, painel, toml)
    projetos = ["loja", " loja ", "", "/home/a/loja"]
    conectores.salvar("x", {"comando": "y", "projetos": projetos}, painel, toml)
    (listado,) = [c for c in conectores.listar(toml, painel, env={}) if c["nome"] == "x"]
    assert listado["projetos"] == ["loja", "/home/a/loja"]


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


# --- o seletor da sessão (19/10/2026): o projeto escolhe os conectores, pelo caminho inteiro ---


def test_caminho_inteiro_isola_pastas_de_mesmo_nome(arquivos: tuple[Path, Path]) -> None:
    toml, painel = arquivos
    joao, maria = Path("/clientes/joao/site"), Path("/clientes/maria/site")
    conectores.salvar("n8n-joao", {"comando": "n8n-mcp"}, painel, toml)
    assert conectores.ligar_no_projeto(joao, ["n8n-joao"], painel=painel, caminho=toml) == [
        "docs",
        "n8n-joao",
    ]
    assert "n8n-joao" in mcp_externo.para_projeto(joao, toml, painel, env={}).servidores
    assert "n8n-joao" not in mcp_externo.para_projeto(maria, toml, painel, env={}).servidores
    (na_maria,) = [c for c in conectores.do_projeto(maria, toml, painel) if c["nome"] == "n8n-joao"]
    assert na_maria == {
        "nome": "n8n-joao",
        "tipo": "stdio",
        "marcado": False,
        "todos": False,
        "editavel": True,
        "outros": ["site"],  # já está noutro projeto: o seletor avisa
    }


def test_desmarcar_tira_o_caminho_e_o_nome_antigo_e_preserva_os_outros(
    arquivos: tuple[Path, Path],
) -> None:
    toml, painel = arquivos
    loja, padaria = Path("/clientes/loja"), Path("/clientes/padaria")
    conectores.ligar_no_projeto(
        padaria, ["erp-loja"], so_adicionar=True, painel=painel, caminho=toml
    )
    # "loja" (o nome antigo) e a padaria: tirar da loja não tira da padaria.
    assert conectores.ligar_no_projeto(loja, [], painel=painel, caminho=toml) == ["docs"]
    (erp,) = [c for c in conectores.listar(toml, painel, env={}) if c["nome"] == "erp-loja"]
    assert erp["projetos"] == ["/clientes/padaria"]
    # "*" vale em todos e não sai por um projeto; nome desconhecido é recusado.
    assert "docs" in mcp_externo.para_projeto(loja, toml, painel, env={}).servidores
    with pytest.raises(McpInvalido, match="desconhecido"):
        conectores.ligar_no_projeto(loja, ["nao-existe"], painel=painel, caminho=toml)


def test_criar_a_sessao_so_soma_conectores(arquivos: tuple[Path, Path]) -> None:
    toml, painel = arquivos
    loja = Path("/clientes/loja")
    valendo = conectores.ligar_no_projeto(
        loja, ["pessoal"], so_adicionar=True, painel=painel, caminho=toml
    )
    assert valendo == ["docs", "erp-loja", "pessoal"]  # o erp-loja continua


def test_colar_o_mesmo_json_para_outro_cliente_pede_outro_nome(
    arquivos: tuple[Path, Path],
) -> None:
    toml, painel = arquivos
    colado = '{"mcpServers": {"docs": {"url": "https://mcp.docs.com/v2"}}}'
    with pytest.raises(McpInvalido, match="Já existe o conector docs"):
        conectores.importar(colado, painel=painel, caminho=toml, novo=True)
    assert conectores.importar(colado, "docs-maria", painel=painel, caminho=toml, novo=True) == [
        "docs-maria"
    ]


# --- a conversa com o Zé (19/10/2026): o conector de um cliente fica nas sessões dele ---------


def test_conversa_recebe_so_os_gerais_e_os_marcados(arquivos: tuple[Path, Path]) -> None:
    toml, painel = arquivos
    assert set(mcp_externo.para_conversa(toml, {}, painel).servidores) == {"pessoal"}
    (erp,) = [c for c in conectores.listar(toml, painel, env={}) if c["nome"] == "erp-loja"]
    assert erp["conversa"] is False
    conectores.salvar("erp-loja", {**_dados(erp), "conversa": True}, painel, toml)
    conversa = mcp_externo.para_conversa(toml, {}, painel)
    assert set(conversa.servidores) == {"pessoal", "erp-loja"}
    assert conversa.livres == ["mcp__erp-loja__listar_pedidos", "mcp__pessoal__ver"]
    assert conversa.bloqueadas == ["mcp__erp-loja__apagar_pedido"]
    # Tirado do último projeto, volta a ser geral, e a marca some.
    conectores.ligar_no_projeto(Path("/clientes/loja"), [], painel=painel, caminho=toml)
    (erp,) = [c for c in conectores.listar(toml, painel, env={}) if c["nome"] == "erp-loja"]
    assert erp["projetos"] == [] and erp["conversa"] is True
    assert "conversa" not in json.loads(painel.read_text())["servidores"]["erp-loja"]


def test_colar_de_novo_mantem_a_marca_da_conversa(arquivos: tuple[Path, Path]) -> None:
    toml, painel = arquivos
    (erp,) = [c for c in conectores.listar(toml, painel, env={}) if c["nome"] == "erp-loja"]
    conectores.salvar("erp-loja", {**_dados(erp), "conversa": True}, painel, toml)
    colado = '{"mcpServers": {"x": {"command": "npx", "args": ["-y", "erp-mcp@2"]}}}'
    conectores.importar(colado, "erp-loja", painel=painel, caminho=toml)
    (erp,) = [c for c in conectores.listar(toml, painel, env={}) if c["nome"] == "erp-loja"]
    assert erp["conversa"] is True and erp["argumentos"] == ["-y", "erp-mcp@2"]


def test_sessoes_listar_mostra_os_conectores_de_cada_projeto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jarvis.cerebro.ferramentas import sessoes as ferramentas_sessoes

    def do_projeto(pasta: Path) -> list[dict[str, object]]:
        marcado = pasta.name == "loja"
        return [{"nome": "n8n-loja", "marcado": marcado}, {"nome": "docs", "marcado": True}]

    monkeypatch.setattr(conectores, "do_projeto", do_projeto)
    assert ferramentas_sessoes._conectores("/clientes/loja") == ["n8n-loja", "docs"]
    assert ferramentas_sessoes._conectores("/clientes/padaria") == ["docs"]


def _dados(c: dict[str, object]) -> dict[str, object]:
    """O conector como o painel manda salvar, a partir do que a lista mostra."""
    chaves = ("tipo", "comando", "argumentos", "url", "ambiente", "cabecalhos", "livres",
              "bloqueadas", "projetos")  # fmt: skip
    return {k: c[k] for k in chaves}
