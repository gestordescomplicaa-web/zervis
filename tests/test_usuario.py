"""O "Quem sou eu": nenhum nome fixo no código; a persona recebe quem usa o Zé."""

import re
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
    """Nome, fuso e caminhos de quem usa vêm da configuração, nunca do código nem da persona.

    "gdautomacao.ia" é a assinatura de autoria (avisos de copyright da AGPL); o usuário da máquina
    ("gdautomacao" sem o ".ia", em caminhos) não pode aparecer.
    """
    pessoais = ("Gabriel", "Recife", "/home/", "~/Work", "orca/projects", ".hermes", "3D-NOVO")
    extensoes = ("py", "js", "html", "md", "json")
    arquivos = [a for ext in extensoes for a in (RAIZ / "jarvis").rglob(f"*.{ext}")]
    for arquivo in arquivos:
        texto = arquivo.read_text()
        achados = [p for p in pessoais if p in texto]
        achados += re.findall(r"gdautomacao(?!\.ia)", texto)
        assert not achados, arquivo
