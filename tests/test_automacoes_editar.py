"""As Automações mandam no que roda sozinho (ADR 0141): editar pelo painel e pela voz.

Caso de 25/11/2026: pedido pela voz ("agende vídeos segunda, quarta e sexta e publique
automaticamente"), o Zé respondeu que "o sistema não deixa publicar sozinho", e o cartão
"Vídeos automáticos" do Marketing agendava por fora das Automações, sem dar para mudar depois.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.automacoes import parametros
from zervis.automacoes.agenda import FUSO, interpretar
from zervis.automacoes.jobs import JobErro, Jobs
from zervis.cerebro import claude
from zervis.cerebro.ferramentas import automacoes as f_automacoes
from zervis.cerebro.ferramentas import marketing as f_marketing
from zervis.oficina.sessoes import Sessoes
from zervis.portal.acoes import Acoes
from zervis.portal.servidor import PedidoInvalido
from zervis.video.videos import Videos

AGORA = datetime(2026, 11, 25, 10, 0, tzinfo=FUSO)  # quarta-feira


def _por_nome(lista: list[Any]) -> dict[str, Any]:
    return {f.name: f for f in lista}


def _chamar(ferramenta: Any, args: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(ferramenta.handler(args))


def _video(jobs: Jobs, publicar: bool = False) -> str:
    texto = Videos.pedido_agendado(["Atendimento no WhatsApp"], 30, publicar)
    return jobs.criar("Vídeo da marca", "cron 0 9 * * 1,4", "video", texto, AGORA).id


@pytest.mark.parametrize(
    ("agenda", "frase", "partes"),
    [
        ("cron 0 9 * * 1,3,5", "Segunda, quarta e sexta, 9h", {"dias": [1, 3, 5], "hora": "09:00"}),
        ("cron 0 9 * * 1-5", "Dias úteis, 9h", {"dias": [1, 2, 3, 4, 5], "hora": "09:00"}),
        ("cron 30 10 * * 2", "Toda terça, 10h30", {"dias": [2], "hora": "10:30"}),
        ("cron 0 8 * * 6", "Todo sábado, 8h", {"dias": [6], "hora": "08:00"}),
        ("cron 0 7 * * *", "Todo dia, 7h", {"dias": list(range(7)), "hora": "07:00"}),
        ("a cada 3d", "A cada 3 dias", {"quantos": 3, "unidade": "d"}),
        ("a cada 1h", "A cada hora", {"quantos": 1, "unidade": "h"}),
        ("cron */15 * * * *", "Agenda personalizada", {}),
        ("2026-12-01 08:00", "Uma vez", {}),
    ],
)
def test_a_agenda_dita_como_gente_e_em_partes(
    agenda: str, frase: str, partes: dict[str, Any]
) -> None:
    assert parametros.frase(agenda) == frase
    assert {k: v for k, v in parametros.partes(agenda).items() if k != "modo"} == partes


def test_o_formulario_volta_a_um_formato_da_agenda() -> None:
    semana = {"modo": "semana", "dias": [5, 1, 3], "hora": "09:00"}
    assert parametros.montar_agenda(semana) == "cron 0 9 * * 1,3,5"
    assert parametros.montar_agenda({"modo": "intervalo", "quantos": 3, "unidade": "d"}) == (
        "a cada 3d"
    )
    unica = {"modo": "uma_vez", "data": "2030-01-02", "hora": "08:30"}
    assert parametros.montar_agenda(unica) == "2030-01-02 08:30"
    for errado in ({"modo": "semana", "dias": [], "hora": "09:00"}, {"modo": "x"}):
        with pytest.raises(parametros.ParametroErro):
            parametros.montar_agenda(errado)
    # As ferramentas de marketing sempre sugeriram "a cada 3d": o "d" passou a valer.
    assert interpretar("a cada 3d").primeira(AGORA) == datetime(2026, 11, 28, 10, 0, tzinfo=FUSO)


def test_editar_muda_o_que_veio_e_recalcula_a_proxima(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path / "jobs.json")
    id_ = _video(jobs)
    jobs.pausar(id_)
    feito = jobs.editar(id_, AGORA, agenda="cron 0 9 * * 1,3,5", nome="  Reels  da semana ")
    assert (feito.nome, feito.agenda) == ("Reels da semana", "cron 0 9 * * 1,3,5")
    assert feito.proxima == "2026-11-27T09:00:00-03:00"  # sexta: a quarta das 9h já passou
    assert not feito.ativo  # pausada, continua pausada
    assert parametros.ler("video", feito.texto)["temas"] == ["Atendimento no WhatsApp"]
    with pytest.raises(JobErro):
        jobs.editar(id_, AGORA, agenda="cron 99 * * * *")
    with pytest.raises(JobErro):
        jobs.editar("nada", AGORA, nome="x")


def test_os_parametros_de_cada_tipo() -> None:
    video = Videos.pedido_agendado([], 30)
    novo = parametros.montar("video", video, {"temas": "IA\nAgenda", "publicar": True, "x": 1})
    assert parametros.ler("video", novo) == {
        "temas": ["IA", "Agenda"],
        "duracao": 30,
        "publicar": True,
    }
    with pytest.raises(parametros.ParametroErro):
        parametros.montar("video", video, {"duracao": 7})
    artigo = parametros.montar("artigo", json.dumps({"tema": ""}), {"publicar": True})
    assert parametros.ler("artigo", artigo) == {"tema": "", "publicar": True}
    assert parametros.montar("lembrete", "Beber água", {"texto": "Alongar"}) == "Alongar"
    # A ligação foi aprovada pela voz com o número e o recado: só o nome e a agenda mudam.
    with pytest.raises(parametros.ParametroErro):
        parametros.montar("ligacao", json.dumps({"numero": "5581"}), {"texto": "outro recado"})


def test_pela_voz_agenda_publicando_sozinho_e_depois_edita(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path / "jobs.json")
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path / "casa",), rodar=lambda *a, **k: "")
    marketing = _por_nome(f_marketing.ferramentas(sessoes, jobs))
    criado = _chamar(
        marketing["marketing_video_agendar"], {"quando": "cron 0 9 * * 1,3,5", "publicar": True}
    )
    assert not criado.get("is_error")
    [job] = jobs.listar()
    assert parametros.ler("video", job.texto)["publicar"] is True

    t = _por_nome(f_automacoes.ferramentas(jobs))
    lista = json.loads(_chamar(t["automacoes_listar"], {})["content"][0]["text"])
    assert lista[0]["quando"] == "Segunda, quarta e sexta, 9h" and lista[0]["publicar"] is True
    r = _chamar(t["automacao_editar"], {"id": job.id, "temas": ["Agenda cheia"], "duracao": 45})
    editada = json.loads(r["content"][0]["text"])
    assert editada["temas"] == ["Agenda cheia"] and editada["duracao"] == 45
    assert editada["publicar"] is True  # o que não foi pedido fica
    assert _chamar(t["automacao_editar"], {"id": "nada", "nome": "x"}).get("is_error")


def test_a_confirmacao_falada_diz_que_publica_sozinho() -> None:
    sozinho = claude.descrever(
        "mcp__jarvis__automacao_editar",
        {"id": "a1", "quando": "cron 0 9 * * 1,3,5", "publicar": True},
    )
    assert "vai ao ar sozinho" in sozinho and "a1" in sozinho
    volta = claude.descrever("mcp__jarvis__automacao_editar", {"id": "a1", "publicar": False})
    assert "esperar a sua aprovação" in volta


def test_o_painel_le_e_edita(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path / "jobs.json")
    id_ = _video(jobs)
    acoes = Acoes(SimpleNamespace(jobs=jobs), tmp_path, tmp_path)
    [lida] = acoes.leituras()["automacoes"]()
    assert lida["agenda_frase"] == "Segunda e quinta, 9h" and lida["tipo_nome"] == "Vídeo"
    assert lida["quando"] == {"modo": "semana", "dias": [1, 4], "hora": "09:00"}
    assert lida["duracoes"] == [15, 30, 45, 60]
    editar = acoes.escritas()["automacao/editar"]
    dados = {
        "id": id_,
        "nome": "Reels",
        "quando": {"modo": "semana", "dias": [1, 3, 5], "hora": "08:30"},
        "parametros": {"temas": "IA\nAgenda", "duracao": 60, "publicar": True},
    }
    [depois] = editar(dados)
    assert depois["agenda_frase"] == "Segunda, quarta e sexta, 8h30"
    assert depois["parametros"] == {"temas": ["IA", "Agenda"], "duracao": 60, "publicar": True}
    with pytest.raises(PedidoInvalido):
        editar({"id": id_, "quando": {"modo": "semana", "dias": [], "hora": "08:30"}})
    with pytest.raises(PedidoInvalido):
        editar({"id": "nada"})


def test_o_marketing_nao_agenda_mais_por_conta_propria(tmp_path: Path) -> None:
    rotas = Acoes(SimpleNamespace(), tmp_path, tmp_path).escritas()
    assert not [r for r in rotas if r.startswith("marketing/") and r.endswith("/agendar")]
    assert "marketing/agendar" not in rotas
