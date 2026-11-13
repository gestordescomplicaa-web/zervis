"""Cada página do painel só alcança os serviços que declara (`dependencias`). Um `self.n.x` sem
declarar quebra a página só no Zé de verdade: nos testes com núcleo falso, passa (13/11/2026:
a página da câmera caiu com `camera_em_conversa`)."""

import ast
from pathlib import Path

ACOES = Path(__file__).resolve().parents[1] / "zervis" / "portal" / "acoes"


def _usados(classe: ast.ClassDef) -> set[str]:
    return {
        no.attr
        for no in ast.walk(classe)
        if isinstance(no, ast.Attribute)
        and isinstance(no.value, ast.Attribute)
        and no.value.attr == "n"
        and isinstance(no.value.value, ast.Name)
        and no.value.value.id == "self"
    }


def _declarados(classe: ast.ClassDef) -> set[str] | None:
    for no in classe.body:
        if (
            isinstance(no, ast.Assign)
            and any(isinstance(a, ast.Name) and a.id == "dependencias" for a in no.targets)
            and isinstance(no.value, ast.Tuple)
        ):
            return {str(ast.literal_eval(e)) for e in no.value.elts}
    return None


def test_toda_pagina_declara_os_servicos_que_usa() -> None:
    faltando = {}
    for arquivo in sorted(ACOES.glob("*.py")):
        for classe in ast.walk(ast.parse(arquivo.read_text())):
            if not isinstance(classe, ast.ClassDef):
                continue
            declarados = _declarados(classe)
            if declarados is None:
                continue
            if sobra := _usados(classe) - declarados:
                faltando[f"{arquivo.name}:{classe.name}"] = sorted(sobra)
    assert not faltando, f"serviços usados sem declarar em `dependencias`: {faltando}"
