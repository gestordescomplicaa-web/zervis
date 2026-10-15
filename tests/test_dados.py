"""Migração recuperável e concorrência real entre processos, sem serviços externos."""

import json
import multiprocessing
import sqlite3
from pathlib import Path

import pytest

from jarvis.atendimento.agente import Registros
from jarvis.atendimento.central import Eventos
from jarvis.dados import Banco


def _escrever(pasta: str, telefone: str) -> None:
    r = Registros(Path(pasta))
    for i in range(50):
        r.anotar(telefone, "cliente", f"mensagem {i}")
        r.pausar(telefone, "Contato", "atendimento humano")


def test_dois_processos_escrevem_sem_perder_registros(tmp_path: Path) -> None:
    contexto = multiprocessing.get_context("spawn")
    processos = [contexto.Process(target=_escrever, args=(str(tmp_path), n)) for n in ("11", "22")]
    for processo in processos:
        processo.start()
    for processo in processos:
        processo.join(30)
        assert processo.exitcode == 0
    r = Registros(tmp_path)
    assert r.memoria()["mensagens"] == 100
    assert len(r.pausados()) == 2
    assert r.buscar("mensagem 49")[0]["texto"] == "mensagem 49"
    with r.banco.conexao() as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert r.banco.arquivo.stat().st_mode & 0o777 == 0o600


def test_importa_uma_vez_preserva_e_nao_ressuscita_ao_apagar(tmp_path: Path) -> None:
    pasta = tmp_path / "atendente"
    (pasta / "conversas").mkdir(parents=True)
    mensagem = {"quando": 123.0, "quem": "cliente", "texto": "quero uma limpeza"}
    (pasta / "conversas" / "11.jsonl").write_text(json.dumps(mensagem) + "\n")
    (pasta / "pausados.json").write_text(
        json.dumps({"11": {"nome": "Ana", "motivo": "pediu", "desde": 1}})
    )
    r = Registros(pasta)
    assert r.historico("11") == [mensagem]
    assert r.pausado("11")
    assert (tmp_path / ".antes-do-sqlite/atendente/conversas/11.jsonl").is_file()
    r.banco.backup(tmp_path / "copia.db")
    with sqlite3.connect(tmp_path / "copia.db") as db:
        assert db.execute("SELECT count(*) FROM mensagens").fetchone()[0] == 1
    assert r.esquecer() == 1
    assert Registros(pasta).buscar("limpeza") == []
    assert Registros(pasta).memoria()["mensagens"] == 0


def test_migracao_interrompida_preserva_arquivo_e_reverte_transacao(tmp_path: Path) -> None:
    (tmp_path / "conversas").mkdir()
    arquivo = tmp_path / "conversas/11.jsonl"
    arquivo.write_text('{"texto":"bom", "quem":"cliente"}\ninválido\n')
    with pytest.raises(ValueError):
        Registros(tmp_path)
    assert arquivo.is_file()
    with sqlite3.connect(tmp_path / "atendimento.db") as db:
        assert db.execute("SELECT count(*) FROM mensagens").fetchone()[0] == 0
    arquivo.write_text('{"texto":"bom", "quem":"cliente"}\n')
    assert Registros(tmp_path).memoria()["mensagens"] == 1


def test_eventos_e_ligacoes_sobrevivem_ao_reinicio(tmp_path: Path) -> None:
    r = Registros(tmp_path)
    Eventos(registros=r).publicar("passou", nome="Ana")
    r.ligacao("11", "atendida", 12.5)
    novo = Registros(tmp_path)
    lista, ultimo = Eventos(registros=novo).depois(0)
    assert ultimo == 1 and lista[0]["nome"] == "Ana"
    with novo.banco.conexao() as db:
        assert db.execute("SELECT duracao FROM ligacoes").fetchone()[0] == 12.5


def test_migracoes_numeradas_e_versao_futura_recusada(tmp_path: Path) -> None:
    def primeira(db: sqlite3.Connection) -> None:
        db.execute("CREATE TABLE exemplo (valor TEXT)")
        db.execute("INSERT INTO exemplo VALUES ('preservado')")

    def segunda(db: sqlite3.Connection) -> None:
        db.execute("ALTER TABLE exemplo ADD COLUMN extra INTEGER DEFAULT 7")

    arquivo = tmp_path / "banco.db"
    Banco(arquivo, (primeira,))
    banco = Banco(arquivo, (primeira, segunda))
    with banco.conexao() as db:
        assert tuple(db.execute("SELECT * FROM exemplo").fetchone()) == ("preservado", 7)
    with pytest.raises(ValueError, match="mais recente"):
        Banco(arquivo, (primeira,))
