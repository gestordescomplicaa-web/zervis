"""MCPs externos: config validada, segredos só do ambiente, livres e desligados."""

from pathlib import Path

import pytest

from zervis.cerebro.claude import descrever
from zervis.cerebro.mcp_externo import McpInvalido, carregar

CONFIG = """
[servidores.github]
tipo = "stdio"
comando = "npx"
argumentos = ["-y", "@modelcontextprotocol/server-github"]
ambiente = ["GITHUB_TOKEN"]
livres = ["search_repositories"]
bloqueadas = ["delete_repository"]

[servidores.agenda]
tipo = "http"
url = "https://agenda.exemplo/mcp"
cabecalhos = { Authorization = "AGENDA_AUTH" }

[servidores.velho]
comando = "x"
ligado = false
"""


def _arquivo(tmp_path: Path, texto: str) -> Path:
    arquivo = tmp_path / "mcp.toml"
    arquivo.write_text(texto)
    return arquivo


def test_carrega_com_segredos_do_ambiente(tmp_path: Path) -> None:
    env = {"GITHUB_TOKEN": "t1", "AGENDA_AUTH": "Bearer t2"}
    externos = carregar(_arquivo(tmp_path, CONFIG), env)
    assert set(externos.servidores) == {"github", "agenda"}
    assert externos.servidores["github"]["env"] == {"GITHUB_TOKEN": "t1"}
    assert externos.servidores["agenda"] == {
        "type": "http",
        "url": "https://agenda.exemplo/mcp",
        "headers": {"Authorization": "Bearer t2"},
    }
    assert externos.livres == ["mcp__github__search_repositories"]
    assert externos.bloqueadas == ["mcp__github__delete_repository"]


def test_as_bloqueadas_somem_da_lista_do_cerebro(tmp_path: Path) -> None:
    from zervis.cerebro.claude import ClaudeBrain

    cerebro = ClaudeBrain("m", [], tmp_path, bloqueadas=["mcp__navegador__browser_evaluate"])
    assert cerebro.opcoes().disallowed_tools == ["mcp__navegador__browser_evaluate"]


def test_sem_a_variavel_o_servidor_fica_desligado(tmp_path: Path) -> None:
    externos = carregar(_arquivo(tmp_path, CONFIG), {"AGENDA_AUTH": "x"})
    assert set(externos.servidores) == {"agenda"}


def test_sem_arquivo_nada_liga(tmp_path: Path) -> None:
    assert carregar(tmp_path / "nao-existe.toml", {}).servidores == {}


@pytest.mark.parametrize(
    ("texto", "erro"),
    [
        ('[servidores.jarvis]\ncomando = "x"\n', "reservado"),
        ('[servidores.a]\ntipo = "http"\nurl = "http://site.com/mcp"\n', "https"),
        ('[servidores.a]\ntipo = "ftp"\n', "stdio ou http"),
        ('[servidores.a]\ncomando = "x"\nsenha = "123"\n', "chave desconhecida"),
        ("[outra]\nx = 1\n", "só a seção"),
        ('[servidores.a]\ncomando = "x"\nlivres = ["f"]\nbloqueadas = ["f"]\n', "livre e bloq"),
    ],
)
def test_config_invalida(tmp_path: Path, texto: str, erro: str) -> None:
    with pytest.raises(McpInvalido, match=erro):
        carregar(_arquivo(tmp_path, texto), {})


def test_frase_de_aprovacao_de_ferramenta_externa() -> None:
    frase = descrever("mcp__github__create_issue", {"repo": "jarvis", "title": "Bug na voz"})
    assert frase == "Vou usar create issue do github: repo jarvis, title Bug na voz."
