"""Consumo de tokens do dia: soma por resposta, vira o dia e o resumo falado."""

from pathlib import Path

from jarvis.cerebro.consumo import Consumo

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
