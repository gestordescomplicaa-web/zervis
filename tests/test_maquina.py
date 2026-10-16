"""A persona descreve a máquina em que o Zé roda, e não um Omarchy fixo (ADR 0034)."""

from pathlib import Path

from jarvis.sistema.maquina import Maquina, nome_do_sistema

PERSONAS = Path(__file__).resolve().parents[1] / "jarvis" / "persona"


def test_nome_do_sistema_vem_do_os_release(tmp_path: Path) -> None:
    arquivo = tmp_path / "os-release"
    arquivo.write_text('NAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04.3 LTS"\nID=ubuntu\n')
    assert nome_do_sistema(arquivo) == "Ubuntu 24.04.3 LTS"
    assert nome_do_sistema(tmp_path / "nao-existe") == "Linux"


def test_cada_maquina_diz_o_que_o_cerebro_pode_fazer() -> None:
    omarchy = Maquina("Arch Linux", omarchy=True, tela=True, audio=True).para_persona()
    assert omarchy.startswith("## Esta máquina") and "ações do Omarchy" in omarchy
    desktop = Maquina("Ubuntu 24.04", omarchy=False, tela=False, audio=True).para_persona()
    assert "com tela, sem as ações do Omarchy" in desktop
    servidor = Maquina("Ubuntu 24.04", omarchy=False, tela=False, audio=False).para_persona()
    assert "servidor sem tela nem áudio (Ubuntu 24.04)" in servidor
    assert "neste servidor não dá" in servidor


def test_persona_nao_fixa_a_maquina_de_ninguem() -> None:
    """Lição de 16/10/2026: numa VPS, o cérebro lia "Omarchy, Arch Linux" e "pelo fone"."""
    for persona in PERSONAS.glob("*.md"):
        texto = persona.read_text()
        assert "Arch Linux" not in texto and "pelo fone" not in texto, persona.name
