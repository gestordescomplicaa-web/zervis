"""Dependências fixadas por versão exata (docs/06-qualidade.md): atualizar é um commit próprio."""

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_dependencias_tem_versao_exata() -> None:
    """Lição de 16/10/2026: `livekit>=` e `segno>=` ficaram com limite aberto apesar da regra."""
    projeto = tomllib.loads(PYPROJECT.read_text())
    todas = projeto["project"]["dependencies"] + projeto["dependency-groups"]["dev"]
    soltas = [d for d in todas if "==" not in d]
    assert not soltas, f"sem versão exata: {soltas}"
