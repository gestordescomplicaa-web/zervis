"""As skills que a pessoa já tem nos agentes aparecem na página Skills (auditoria 4)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from zervis.cerebro import contas
from zervis.habilidades import skills


def test_descricao_em_varias_linhas() -> None:
    texto = "---\nname: diagnose-crash\ndescription: >\n  Diagnose why a program\n  crashed.\n---\n"
    assert skills._descricao(texto) == ("diagnose-crash", "Diagnose why a program crashed.")
    assert skills._descricao("---\nname: x\ndescription: Uma linha\n---\n") == ("x", "Uma linha")
    assert skills._descricao("sem front matter") == ("", "")


def test_lista_as_skills_da_conta_em_uso_de_cada_agente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "claude/skills/resumo").mkdir(parents=True)
    (tmp_path / "claude/skills/resumo/SKILL.md").write_text(
        "---\nname: resumo\ndescription: Como faço o resumo do dia\n---\n"
    )

    class _Contas:
        def em_uso(self, agente: str) -> SimpleNamespace:
            return SimpleNamespace(onde=tmp_path / agente)

    monkeypatch.setattr(contas, "Contas", _Contas)
    assert skills.dos_agentes() == [
        {"agente": "claude", "nome": "resumo", "descricao": "Como faço o resumo do dia"}
    ]
