"""O "Quem sou eu": nenhum nome fixo no código; a persona recebe quem usa o Zé."""

import re
from pathlib import Path

from zervis import usuario

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
    extensoes = ("py", "js", "html", "md", "json", "go", "toml", "sh")
    arquivos = [a for ext in extensoes for a in (RAIZ / "zervis").rglob(f"*.{ext}")]
    for arquivo in arquivos:
        texto = arquivo.read_text()
        achados = [p for p in pessoais if p.lower() in texto.lower()]  # "gabriel" também
        achados += re.findall(r"gdautomacao(?!\.ia)", texto)
        assert not achados, arquivo


def test_imagens_sem_metadados_de_quem_as_criou() -> None:
    """O Blender grava no PNG o caminho do arquivo de origem (com o usuário da máquina): uma
    imagem do avatar levava um, em 20/10/2026. Os blocos de texto do PNG não entram no projeto."""
    import struct

    for arquivo in (RAIZ / "zervis").rglob("*.png"):
        dados, i, textos = arquivo.read_bytes(), 8, []
        while i < len(dados):
            tamanho = struct.unpack(">I", dados[i : i + 4])[0]
            if dados[i + 4 : i + 8] in (b"tEXt", b"iTXt", b"zTXt"):
                textos.append(dados[i + 8 : i + 8 + tamanho][:60])
            i += 12 + tamanho
        assert not textos, (arquivo, textos)
