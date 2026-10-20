"""O pacote se chama `zervis` desde 20/10/2026; as instalações de antes ainda sobem.

A unidade do systemd antiga roda `python -m jarvis`, e a Central de Atendimento pode estar no ar
como `python -m jarvis.atendimento` quando o `zervis update` troca o código. As duas entradas
repassam para o `zervis` até o próximo `make instalar`.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

from zervis import __version__

RAIZ = Path(__file__).resolve().parents[1]


def test_a_unidade_antiga_sobe_o_zervis() -> None:
    saida = subprocess.run(
        [sys.executable, "-m", "jarvis", "--version"],
        capture_output=True, text=True, timeout=60, check=False,
    )  # fmt: skip
    assert saida.returncode == 0, saida.stderr
    assert saida.stdout.strip().endswith(__version__)


def test_a_central_antiga_acha_a_entrada_nova() -> None:
    especificacao = importlib.util.find_spec("jarvis.atendimento.__main__")
    assert especificacao is not None and especificacao.origin is not None
    assert "zervis.atendimento" in Path(especificacao.origin).read_text()


def test_a_unidade_nova_roda_o_zervis() -> None:
    unidade = (RAIZ / "systemd" / "zervis.service").read_text()
    assert "-m zervis\n" in unidade and "-m jarvis" not in unidade


def test_a_transicao_nao_guarda_codigo() -> None:
    """Só as duas entradas: o resto do Zé mora em `zervis/`."""
    arquivos = sorted(str(p.relative_to(RAIZ)) for p in (RAIZ / "jarvis").rglob("*.py"))
    assert arquivos == [
        "jarvis/__init__.py",
        "jarvis/__main__.py",
        "jarvis/atendimento/__init__.py",
        "jarvis/atendimento/__main__.py",
    ]
