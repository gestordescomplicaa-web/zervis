"""Importação dos formatos existentes e escrita por processos independentes."""

import json
import multiprocessing
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from jarvis.atividade import Atividade
from jarvis.automacoes.jobs import Job, Jobs
from jarvis.cerebro.consumo import Consumo
from jarvis.memoria.conversas import FUSO, Conversas
from jarvis.memoria.linha import LinhaDoTempo
from jarvis.oficina.sessoes import Sessao, Sessoes


def test_importa_conversas_linha_atividade_e_preserva_busca(tmp_path: Path) -> None:
    c = tmp_path / "conversas"
    c.mkdir()
    (c / "2026-10-14.jsonl").write_text(
        json.dumps(
            {
                "em": "2026-10-14T10:00:00-03:00",
                "fala_antiga": "cadê a proposta?",
                "ze": "Em revisão.",
            }
        )
        + "\n"
    )
    linha = tmp_path / "linha.jsonl"
    linha.write_text(
        json.dumps(
            {
                "quando": "2026-10-14T10:00:00-03:00",
                "registrado": "2026-10-14T10:00:00-03:00",
                "tipo": "marco",
                "texto": "Lançamento da proposta.",
            }
        )
        + "\n"
    )
    atividade = tmp_path / "atividade.jsonl"
    atividade.write_text(
        json.dumps({"quando": 1, "tipo": "execucao", "titulo": "Revisou a proposta."}) + "\n"
    )
    assert Conversas(c).buscar("proposta")[0].ze == "Em revisão."
    assert Conversas(c).dias() == [date(2026, 10, 14)]
    assert LinhaDoTempo(linha).buscar("proposta")[0].tipo == "marco"
    assert Atividade(atividade).buscar("proposta")[0]["tipo"] == "execucao"
    assert len(Conversas(c).do_dia(date(2026, 10, 14))) == 1
    assert (c / ".antes-do-sqlite/2026-10-14.jsonl").is_file()


def test_importa_sessao_mensagens_agendamentos_e_consumo(tmp_path: Path) -> None:
    pasta = tmp_path / "sessoes"
    s = Sessao(id="1234abcd", nome="Importada", pasta=str(tmp_path))
    d = pasta / s.id
    d.mkdir(parents=True)
    (d / "sessao.json").write_text(json.dumps(asdict(s)))
    (d / "mensagens.jsonl").write_text('{"quem":"usuario","texto":"proposta","em":"hoje"}\n')
    sessoes = Sessoes(pasta, (tmp_path,), rodar=lambda *_: None)
    assert sessoes.ler(s.id) == s
    assert sessoes.buscar(s.id, "proposta")[0]["texto"] == "proposta"
    assert Sessoes(pasta, (tmp_path,), rodar=lambda *_: None).mensagens(s.id) == sessoes.mensagens(
        s.id
    )
    job = Job("Revisão", "em 1m", "lembrete", "Revisar.", datetime.now(FUSO).isoformat())
    arquivo = tmp_path / "jobs.json"
    arquivo.write_text(json.dumps([asdict(job)]))
    assert Jobs(arquivo).listar() == [job]
    consumo = tmp_path / "consumo.json"
    consumo.write_text(
        json.dumps(
            {
                "dia": date.today().isoformat(),
                "respostas": 3,
                "entrada": 12,
                "cache_lido": 0,
                "cache_criado": 0,
                "saida": 4,
                "locais": 0,
            }
        )
    )
    assert Consumo(consumo).retrato()["respostas"] == 3
    assert (tmp_path / ".antes-do-sqlite/jobs.json").is_file()


def _escrever(raiz: str, indice: int) -> None:
    pasta = Path(raiz)
    jobs, consumo = Jobs(pasta / "jobs.json"), Consumo(pasta / "consumo.json")
    for i in range(10):
        jobs.criar(f"{indice}-{i}", "em 1m", "lembrete", "Revisar.", datetime.now(FUSO))
        consumo.somar({"input_tokens": 1, "output_tokens": 1}, "teste")


def test_agendamentos_e_consumo_nao_perdem_escritas_entre_processos(tmp_path: Path) -> None:
    contexto = multiprocessing.get_context("spawn")
    processos = [contexto.Process(target=_escrever, args=(str(tmp_path), n)) for n in (1, 2)]
    for processo in processos:
        processo.start()
    for processo in processos:
        processo.join(30)
        assert processo.exitcode == 0
    assert len(Jobs(tmp_path / "jobs.json").listar()) == 20
    assert Consumo(tmp_path / "consumo.json").retrato()["respostas"] == 20
