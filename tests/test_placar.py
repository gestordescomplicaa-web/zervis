"""O placar (plano de maturidade, Frente 3): latência por caminho, nota por área, a queda da
rodada noturna e o Markdown público, sem nenhuma fala nem resposta."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from zervis import lugares
from zervis.avaliacao import placar
from zervis.avisos.fila import Fila
from zervis.voz import latencia


def _turno(total: float, resultado: str = "concluido", **campos: Any) -> dict[str, Any]:
    base = {"versao": 1, "origem": "voz", "rota": "cerebro", "provedor": "claude"}
    return {**base, **campos, "resultado": resultado, "etapas_ms": {"total": total}}


def test_cada_turno_cai_no_seu_caminho() -> None:
    assert latencia.caminho(_turno(1, provedor="rapida:plano")) == ("recorte", "via_rapida")
    assert latencia.caminho(_turno(1, fim_por="live")) == ("ao_vivo", "cerebro")
    assert latencia.caminho(_turno(1, rota="controle")) == ("recorte", "comando")
    assert latencia.caminho(_turno(1, origem="teclado")) is None  # não é voz
    assert latencia.caminho(_turno(1, rota="manutencao")) is None  # a captura antiga (ADR 0072)


def test_p50_e_p95_so_dos_turnos_que_falaram() -> None:
    turnos = [_turno(float(ms), provedor="rapida:plano") for ms in range(100, 2100, 100)]
    turnos += [
        _turno(9999, "sem_som", provedor="rapida:plano"),
        _turno(9999, "interrompido", provedor="rapida:plano"),  # cortado: não é falha
    ]
    (g,) = latencia.por_caminho(turnos)
    assert (g["caminho"], g["turnos"], g["n"]) == ("via_rapida", 22, 20)
    assert (g["p50_ms"], g["p95_ms"], g["falhas"]) == (1000.0, 1900.0, 1)


def test_le_os_ultimos_dias(tmp_path: Path) -> None:
    for dia in ("2026-11-07", "2026-11-08", "2026-11-09"):
        (tmp_path / f"{dia}.jsonl").write_text(json.dumps(_turno(1)) + "\n")
    assert len(latencia.ler_dias(tmp_path, 2, date(2026, 11, 9))) == 2


def _relatorio(notas: dict[str, list[bool]], **extra: Any) -> dict[str, Any]:
    cenarios = [
        {
            "arquivo": f"{area}-{i}",
            "area": area,
            "rodadas": [{"passou": p, "tokens": 1000, "resposta": "Mandei para a Marta."}],
        }
        for area, ps in notas.items()
        for i, p in enumerate(ps)
    ]
    return {"quando": "2026-11-09T03:00:00", "rotulo": "claude:x", "cenarios": cenarios, **extra}


def test_queda_de_mais_de_cinco_pontos_vira_aviso() -> None:
    antes = _relatorio({"voz": [True] * 10, "sessoes": [True] * 10})
    agora = _relatorio({"voz": [True] * 9 + [False], "sessoes": [True] * 10})  # 100 → 90
    caidas = placar.quedas(agora, antes)
    assert caidas == [("voz", 100.0, 90.0)]
    assert placar.aviso_de_queda(caidas) == (
        "A avaliação noturna caiu em Voz e fala curta, de 100 para 90."
    )
    leve = _relatorio({"voz": [True] * 19 + [False], "sessoes": [True] * 10})  # 95: só 5
    assert placar.quedas(leve, antes) == []


def test_o_placar_usa_a_ultima_noturna_e_nao_mostra_respostas(tmp_path: Path) -> None:
    (tmp_path / "20261101-030000.json").write_text(
        json.dumps(_relatorio({"voz": [True]}, noturna=True))
    )
    (tmp_path / "20261102-100000.json").write_text(json.dumps(_relatorio({"voz": [False]})))
    escolhida = placar.completa(tmp_path, total=100)
    assert escolhida is not None and escolhida.get("noturna")
    texto = placar.markdown(
        escolhida, latencia.por_caminho([_turno(1500, provedor="rapida:plano")]), "0.4.0", 7
    )
    assert (
        "Versão 0.4.0" in texto and "**100%**" in texto and "| Voz e fala curta | 100% |" in texto
    )
    assert "| Recorte | Via rápida | 1 | 1,5 s | 1,5 s | 0 |" in texto
    assert "Marta" not in texto  # o repositório é público


def test_sem_noturna_so_uma_rodada_com_metade_dos_cenarios(tmp_path: Path) -> None:
    (tmp_path / "20261101-030000.json").write_text(json.dumps(_relatorio({"voz": [True] * 3})))
    assert placar.completa(tmp_path, total=100) is None
    assert "Ainda sem rodada completa" in placar.markdown(None, [], "0.4.0", 7)


def test_a_queda_chega_ao_ze_pela_fila_duravel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zervis.avaliacao import __main__ as cli

    monkeypatch.setattr(lugares, "ESTADO", tmp_path)
    cli.avisar_queda("A avaliação noturna caiu em Ligações, de 90 para 70.")
    (aviso,) = Fila(tmp_path / "avisos.json").validos()
    assert aviso.origem == "avaliacao" and "Ligações" in aviso.texto
