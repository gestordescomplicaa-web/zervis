"""Garante que o pacote instala, importa e o ponto de entrada responde."""

import pytest

from jarvis import __version__
from jarvis.__main__ import main


def test_versao_vem_do_pyproject() -> None:
    assert __version__ == "0.0.1"


def test_main_mostra_versao(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out == f"jarvisd {__version__}\n"


def test_main_recusa_argumento_desconhecido(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--qualquer"]) == 2
    assert "desconhecido" in capsys.readouterr().err
