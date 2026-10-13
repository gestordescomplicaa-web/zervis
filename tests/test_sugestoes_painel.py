"""As sugestões que o Zé aprende sozinho, no painel (auditoria 3, achado 1)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.habilidades import revisao
from jarvis.habilidades.diario import Diario
from jarvis.habilidades.skills import Skills
from jarvis.memoria.curta import Memoria
from jarvis.portal.acoes import Acoes
from jarvis.portal.servidor import PedidoInvalido


def _acoes(tmp_path: Path) -> Acoes:
    a = Acoes.__new__(Acoes)
    a.n = SimpleNamespace(  # type: ignore[assignment]
        memoria=Memoria(tmp_path / "memoria", {"usuario": 2000, "jarvis": 2000}),
        skills=Skills(tmp_path / "skills"),
        pendencias=revisao.Pendencias(tmp_path / "pendencias.json"),
        diario=Diario(tmp_path / "diario.jsonl"),
    )
    return a


def _sugestao(texto: str) -> revisao.Proposta:
    dados = {"acao": "adicionar", "alvo": "usuario", "texto": texto, "antigo": ""}
    return revisao.Proposta("memoria", dados, f"guardar na memória sobre você: {texto}")


def test_aparece_e_aprovar_grava_na_memoria(tmp_path: Path) -> None:
    a = _acoes(tmp_path)
    a.n.pendencias.adicionar([_sugestao("Prefere respostas curtas.")])
    m = a.memoria()
    assert len(m["sugestoes"]) == 1 and m["sugestoes"][0]["tipo"] == "memoria"
    r = a.decidir_sugestao({"id": m["sugestoes"][0]["id"], "aprovar": True})
    assert r["aviso"] == "Aprovada." and r["sugestoes"] == []
    assert "Prefere respostas curtas." in r["usuario"]


def test_descartar_tira_sem_gravar(tmp_path: Path) -> None:
    a = _acoes(tmp_path)
    a.n.pendencias.adicionar([_sugestao("Gosta de café.")])
    id_ = a.memoria()["sugestoes"][0]["id"]
    r = a.decidir_sugestao({"id": id_, "aprovar": False})
    assert r["aviso"] == "Descartada." and r["usuario"] == [] and r["sugestoes"] == []
    with pytest.raises(PedidoInvalido):
        a.decidir_sugestao({"id": id_, "aprovar": True})
