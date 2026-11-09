"""Consumo de tokens do dia: soma por resposta, vira o dia e o resumo falado."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from zervis.cerebro.consumo import Consumo, da_atividade, gasto

TURNO = {
    "input_tokens": 2,
    "cache_creation_input_tokens": 83,
    "cache_read_input_tokens": 6353,
    "output_tokens": 16,
}


def test_soma_o_dia_e_sobrevive_a_reinicio(tmp_path: Path) -> None:
    consumo = Consumo(tmp_path / "consumo.json")
    assert consumo.resumo_falado() == "Hoje ainda não respondi nada pelo cérebro."
    consumo.somar(TURNO, "claude")
    consumo.somar(TURNO, "claude")
    consumo.somar(None, "claude")  # resposta interrompida: nada a somar
    reaberto = Consumo(tmp_path / "consumo.json")
    assert reaberto.hoje["respostas"] == 2
    assert reaberto.hoje["cache_lido"] == 2 * 6353
    assert reaberto.resumo_falado() == (
        "Hoje foram 2 respostas, com 13 mil tokens lidos, 99% do cache, e 32 escritos."
    )


def test_dia_novo_zera(tmp_path: Path) -> None:
    arquivo = tmp_path / "consumo.json"
    arquivo.write_text(
        '{"dia": "2026-10-05", "respostas": 9, "entrada": 1, "cache_lido": 1, '
        '"cache_criado": 1, "saida": 1}'
    )
    consumo = Consumo(arquivo)
    consumo.somar(TURNO, "claude")
    assert consumo.hoje["respostas"] == 1


def test_dia_anterior_vai_para_o_historico(tmp_path: Path) -> None:
    arquivo = tmp_path / "consumo.json"
    arquivo.write_text(
        '{"dia": "2026-10-05", "respostas": 9, "entrada": 1, "cache_lido": 1, '
        '"cache_criado": 1, "saida": 1}'
    )
    consumo = Consumo(arquivo)
    assert consumo.retrato()["respostas"] == 0  # virou o dia ao olhar
    consumo.somar(TURNO, "claude")
    assert [d["dia"] for d in Consumo(arquivo).historico()] == ["2026-10-05"]
    assert consumo.historico()[0]["respostas"] == 9


def test_o_custo_de_cada_pedido_vai_para_a_atividade() -> None:
    """Plano de maturidade, Frente 3: o custo por tarefa na Atividade, por parte."""
    uso = {"input_tokens": 200, "cache_read_input_tokens": 3000, "output_tokens": 50}
    partes = [
        gasto({"input_tokens": 900, "output_tokens": 20}, "rapida", "claude-sonnet-5-5"),
        gasto(uso, "completo", "claude-opus-5-5"),
        gasto({"input_tokens": 300}, "pesquisa"),
    ]
    assert da_atividade({"provedor": "claude", "partes": partes, "ferramentas": []}) == {
        "consumo": 4470,
        "consumo_partes": "via rápida 920 · cérebro 3,2 mil · pesquisa 300",
    }
    assert da_atividade(None) == {}  # comando local: não chamou modelo


def test_o_pedido_na_atividade_leva_o_custo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zervis import atividade
    from zervis.nucleo.servicos.memoria import ServicoMemoria

    registro = atividade.Atividade(tmp_path / "atividade.db")
    monkeypatch.setattr(atividade, "PADRAO", registro)
    n = SimpleNamespace(
        voz=SimpleNamespace(muda=False),
        _gasto_do_turno={"partes": [gasto({"input_tokens": 1500}, "completo")]},
        conversas=SimpleNamespace(registrar=lambda *_: (_ for _ in ()).throw(OSError("x"))),
        _pedido_quando=0.0,
    )
    ServicoMemoria(n)._registrar_turno({"pessoa": "Que horas são?", "jarvis": "Três e meia."})
    (item,) = registro.listar(tipos=("pedido",))
    assert item["consumo"] == 1500 and item["consumo_partes"] == "cérebro 1,5 mil"
