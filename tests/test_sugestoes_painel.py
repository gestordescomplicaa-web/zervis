"""As sugestões que o Zé aprende sozinho, no painel (auditoria 3, achado 1)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from zervis.habilidades import revisao
from zervis.habilidades.diario import Diario
from zervis.habilidades.skills import Skills
from zervis.memoria.curta import Memoria
from zervis.portal.acoes import Acoes
from zervis.portal.servidor import PedidoInvalido


def _acoes(tmp_path: Path) -> Acoes:
    a = Acoes.__new__(Acoes)
    a.n = SimpleNamespace(
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


def test_memoria_dos_projetos_conta_as_paginas(tmp_path: Path) -> None:
    import sqlite3

    from zervis.memoria import aimemory

    (tmp_path / "db").mkdir()
    with sqlite3.connect(tmp_path / "db" / "memory.sqlite") as con:
        con.execute("create table pages (id integer, is_latest integer)")
        con.executemany("insert into pages values (?, ?)", [(1, 1), (2, 1), (3, 0)])
    s = aimemory.situacao("http://127.0.0.1:1", tmp_path)
    assert s == {"ativa": False, "paginas": 2}
    assert aimemory.situacao("http://127.0.0.1:1", tmp_path / "nada")["paginas"] is None
