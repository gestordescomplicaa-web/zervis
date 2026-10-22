"""O explorador da pasta de uma sessão: preso à pasta, marca o ignorado, busca e mostra."""

from pathlib import Path

import pytest

from zervis.oficina import arquivos
from zervis.oficina.sessoes import SessaoErro, Sessoes, _git


@pytest.fixture
def projeto(tmp_path: Path) -> Path:
    p = tmp_path / "loja"
    (p / "src").mkdir(parents=True)
    (p / "src/app.py").write_text("def preco():\n    return 10  # TODO desconto\n")
    (p / "README.md").write_text("# Loja\n")
    (p / ".gitignore").write_text("build/\n*.log\n")
    (p / "build").mkdir()
    (p / "erro.log").write_text("x")
    (p / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 20)
    assert _git(p, "init", "-q").returncode == 0
    return p


def test_lista_pastas_primeiro_e_marca_o_ignorado(projeto: Path) -> None:
    itens = arquivos.listar(projeto)
    nomes = [i["nome"] for i in itens]
    assert nomes[:2] == ["build", "src"] and ".git" not in nomes
    marcados = {i["nome"]: i["ignorado"] for i in itens}
    assert marcados["build"] and marcados["erro.log"] and not marcados["README.md"]
    assert [i["caminho"] for i in arquivos.listar(projeto, "src")] == ["src/app.py"]


def test_nunca_sai_da_pasta(projeto: Path, tmp_path: Path) -> None:
    (tmp_path / "segredo.txt").write_text("senha")
    (projeto / "atalho").symlink_to(tmp_path / "segredo.txt")
    for ruim in ("../segredo.txt", "atalho", "src/../../segredo.txt", ".git/config"):
        with pytest.raises(arquivos.ArquivoErro):
            arquivos.ler(projeto, ruim)
    with pytest.raises(arquivos.ArquivoErro):
        arquivos.listar(projeto, "..")


def test_mostra_texto_imagem_e_binario(projeto: Path) -> None:
    assert arquivos.ler(projeto, "README.md")["texto"] == "# Loja\n"
    imagem = arquivos.ler(projeto, "logo.png")
    assert imagem["tipo"] == "imagem" and imagem["url"].startswith("data:image/png;base64,")
    (projeto / "dados.bin").write_bytes(b"\0\1\2" * 10)
    assert arquivos.ler(projeto, "dados.bin")["tipo"] == "binario"


def test_busca_por_nome_e_por_conteudo(projeto: Path) -> None:
    assert arquivos.buscar(projeto, "app") == [{"caminho": "src/app.py"}]
    achados = arquivos.buscar(projeto, "todo desconto", "conteudo")
    assert achados == [
        {"caminho": "src/app.py", "linha": 2, "trecho": "return 10  # TODO desconto"}
    ]
    assert arquivos.buscar(projeto, "x") == []  # termo curto demais


def test_projeto_novo_nasce_com_git_e_readme(tmp_path: Path) -> None:
    raiz = tmp_path / "casa"
    (raiz / "projetos").mkdir(parents=True)
    sessoes = Sessoes(tmp_path / "sessoes", (raiz,), projetos_novos=raiz / "projetos")
    pasta = sessoes.criar_projeto("Minha Loja Nova")
    assert pasta == raiz / "projetos/Minha-Loja-Nova"
    assert (pasta / "README.md").read_text() == "# Minha Loja Nova\n"
    assert _git(pasta, "rev-parse", "--is-inside-work-tree").stdout.strip() == "true"
    s = sessoes.criar("Loja", str(pasta))
    assert s.pasta == str(pasta)
    with pytest.raises(SessaoErro, match="já existe"):
        sessoes.criar_projeto("Minha Loja Nova")
    with pytest.raises(SessaoErro, match="nome"):
        sessoes.criar_projeto("///")
