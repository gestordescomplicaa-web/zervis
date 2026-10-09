"""Fase 7: agendas, automações duráveis, fila de avisos com resumo e lembretes da agenda."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from jarvis.automacoes.agenda import FUSO, AgendaInvalida, interpretar
from jarvis.automacoes.calendario import Calendario
from jarvis.automacoes.jobs import JobErro, Jobs
from jarvis.avisos.fila import Fila

AGORA = datetime(2026, 10, 6, 20, 50, tzinfo=FUSO)  # terça-feira


@pytest.mark.parametrize(
    ("texto", "primeira", "seguinte"),
    [
        ("em 2m", "06 20:52", None),
        ("Em 1h30m", "06 22:20", None),
        ("a cada 2h", "06 22:50", "07 00:50"),
        ("cron 0 9 * * 1-5", "07 09:00", "08 09:00"),
        ("cron */15 * * * *", "06 21:00", "06 21:15"),
        ("cron 0 10 * * 0", "11 10:00", "18 10:00"),  # domingo
        ("2026-10-07 08:00", "07 08:00", None),
    ],
)
def test_quatro_formatos(texto: str, primeira: str, seguinte: str | None) -> None:
    a = interpretar(texto)
    p = a.primeira(AGORA)
    assert p.strftime("%d %H:%M") == primeira
    s = a.seguinte(p)
    assert (s.strftime("%d %H:%M") if s else None) == seguinte


@pytest.mark.parametrize(
    "texto", ["daqui a pouco", "em 5s", "a cada 20s", "cron 61 * * * *", "cron 1 2 3"]
)
def test_agenda_invalida(texto: str) -> None:
    with pytest.raises(AgendaInvalida):
        interpretar(texto).primeira(AGORA)


def test_data_no_passado_e_recusada() -> None:
    with pytest.raises(AgendaInvalida, match="passou"):
        interpretar("2026-10-06 08:00").primeira(AGORA)


def test_lembrete_unico_roda_uma_vez_e_sobrevive_a_reinicio(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path / "jobs.json")
    job = jobs.criar("", "em 2m", "lembrete", "Beber água.", AGORA)
    assert jobs.vencidos(AGORA) == []
    depois = AGORA + timedelta(minutes=2)
    assert [j.id for j in Jobs(tmp_path / "jobs.json").vencidos(depois)] == [job.id]
    feito = jobs.registrar(job.id, "ok", depois)
    assert (feito.ultimo_status, feito.proxima, feito.ativo) == ("ok", "", False)
    assert jobs.vencidos(depois + timedelta(hours=1)) == []


def test_intervalo_nao_repoe_execucoes_perdidas(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path / "jobs.json")
    job = jobs.criar("água", "a cada 1h", "lembrete", "Beber água.", AGORA)
    muito_depois = AGORA + timedelta(hours=5)  # jarvisd ficou parado
    assert len(jobs.vencidos(muito_depois)) == 1
    feito = jobs.registrar(job.id, "ok", muito_depois)
    assert datetime.fromisoformat(feito.proxima) == muito_depois + timedelta(hours=1)


def test_pausar_retomar_remover_e_validacao(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path / "jobs.json")
    job = jobs.criar("bom dia", "cron 0 8 * * *", "pergunta", "Diga a previsão.", AGORA)
    jobs.pausar(job.id)
    assert jobs.vencidos(AGORA + timedelta(days=2)) == []
    retomado = jobs.retomar(job.id, AGORA + timedelta(days=2))
    assert retomado.ativo and retomado.proxima.startswith("2026-10-09T08:00")
    jobs.remover(job.id)
    assert jobs.listar() == []
    with pytest.raises(JobErro, match="tipo"):
        jobs.criar("x", "em 2m", "script", "rm -rf", AGORA)
    with pytest.raises(JobErro, match="duração"):
        jobs.criar("x", "em pouco", "lembrete", "oi", AGORA)


def test_fila_um_aviso_ou_resumo_unico_e_validade(tmp_path: Path) -> None:
    fila = Fila(tmp_path / "avisos.json")
    assert fila.tirar_tudo() is None
    fila.guardar("O Codex terminou: deu certo.")
    assert Fila(tmp_path / "avisos.json").tirar_tudo() == "O Codex terminou: deu certo."
    fila.guardar("Lembrete: beber água.")
    fila.guardar("Daqui a 5 minutos: reunião.", "agenda", expira=1.0)  # já expirou
    fila.guardar("Tenho uma sugestão para você aprovar.")
    assert fila.tirar_tudo() == (
        "Enquanto isso, 2 avisos: Lembrete: beber água; Tenho uma sugestão para você aprovar."
    )
    assert fila.tirar_tudo() is None


def _cache(tmp_path: Path, agora: datetime, eventos: list[dict[str, Any]]) -> Path:
    cache = tmp_path / "calendar-events.json"
    cache.write_text(json.dumps({"version": 1, "syncedAt": agora.isoformat(), "events": eventos}))
    return cache


def test_agenda_avisa_15_e_5_minutos_uma_vez_cada(tmp_path: Path) -> None:
    reuniao = AGORA + timedelta(minutes=14)
    ev = {
        "id": "r1",
        "start": reuniao.isoformat(),
        "end": (reuniao + timedelta(hours=1)).isoformat(),
        "title": "Reunião com o JEV",
    }
    dia_todo = {
        "id": "f",
        "start": AGORA.isoformat(),
        "end": AGORA.isoformat(),
        "allDay": True,
        "title": "Feriado",
    }
    cal = Calendario(tmp_path / "enviados.json", _cache(tmp_path, AGORA, [ev, dia_todo]))
    t = AGORA.timestamp()
    assert [a for a, _ in cal.vencidos(t)] == ["Daqui a 14 minutos: Reunião com o JEV."]
    assert cal.vencidos(t + 60) == []  # o de 15 já foi
    assert [a for a, _ in cal.vencidos(t + 10 * 60)] == ["Daqui a 4 minutos: Reunião com o JEV."]
    assert cal.vencidos(t + 15 * 60) == []  # já começou


def test_agenda_velha_nao_avisa(tmp_path: Path) -> None:
    reuniao = AGORA + timedelta(minutes=10)
    ev = {"id": "r1", "start": reuniao.isoformat(), "title": "Reunião"}
    cache = _cache(tmp_path, AGORA - timedelta(hours=1), [ev])
    assert Calendario(tmp_path / "enviados.json", cache).vencidos(AGORA.timestamp()) == []
