"""Garante que o pacote instala, importa e o ponto de entrada responde."""

from importlib.resources import files
from pathlib import Path

import pytest

from zervis import __version__
from zervis.__main__ import main


def test_versao_vem_do_pyproject() -> None:
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    assert __version__ == tomllib.loads(pyproject.read_text())["project"]["version"]


def test_main_mostra_versao(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out == f"jarvisd {__version__}\n"


def test_main_recusa_argumento_desconhecido(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--qualquer"]) == 2
    assert "desconhecido" in capsys.readouterr().err


def test_personas_sao_recursos_do_pacote() -> None:
    for nome in ("ZE", "RAPIDO"):
        texto = files("zervis").joinpath("persona", f"{nome}.md").read_text()
        assert texto.startswith("# Zé") and "Como responder" in texto


def test_personas_do_processo_anterior_continuam_legiveis() -> None:
    # Um serviço já em execução ainda tem o caminho antigo carregado até ser reiniciado.
    raiz = Path(__file__).resolve().parents[1]
    # JARVIS.md era o nome da persona até 20/10/2026: o link antigo leva à persona nova.
    for antigo_nome, nome in (("JARVIS", "ZE"), ("ZE", "ZE"), ("RAPIDO", "RAPIDO")):
        antigo = raiz / "persona" / f"{antigo_nome}.md"
        atual = files("zervis").joinpath("persona", f"{nome}.md")
        assert antigo.is_symlink() and antigo.read_text() == atual.read_text()
