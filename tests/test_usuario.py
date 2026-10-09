"""O "Quem sou eu": nenhum nome fixo no código; a persona recebe quem usa o Zé."""

from pathlib import Path

from jarvis import usuario

RAIZ = Path(__file__).resolve().parents[1]


def test_perfil_vai_para_a_persona_e_para_as_falas(tmp_path: Path) -> None:
    arquivo = tmp_path / "perfil.json"
    assert usuario.ler(arquivo) == usuario.Perfil()
    usuario.gravar(usuario.Perfil("Ana", "Designer; prefere respostas curtas."), arquivo)
    p = usuario.ler(arquivo)
    assert p.vocativo("Bom dia") == "Bom dia, Ana" and p.rotulo == "Ana"
    assert "Você atende Ana." in p.para_persona() and "Designer" in p.para_persona()
    sem = usuario.Perfil()
    assert sem.vocativo("Bom dia") == "Bom dia" and sem.rotulo == "Usuário"
    assert "pergunte o nome" in sem.para_persona()


def test_nada_de_quem_escreveu_o_ze_no_codigo() -> None:
    """Nome, fuso e caminhos de quem usa vêm da configuração, nunca do código nem da persona."""
    pessoais = ("Gabriel", "Recife", "/home/", "gdautomacao", "~/Work", "orca/projects", ".hermes")
    arquivos = [*(RAIZ / "jarvis").rglob("*.py"), *(RAIZ / "jarvis").rglob("*.js")]
    arquivos += [RAIZ / "persona/JARVIS.md", RAIZ / "persona/RAPIDO.md"]
    for arquivo in arquivos:
        texto = arquivo.read_text()
        assert not [p for p in pessoais if p in texto], arquivo
