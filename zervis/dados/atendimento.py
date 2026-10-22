"""Registros do atendimento; os ajustes e os segredos continuam fora do banco."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from zervis.dados import Banco


def _esquema(db: sqlite3.Connection) -> None:
    for sql in (
        "CREATE TABLE contatos (telefone TEXT PRIMARY KEY)",
        "CREATE TABLE mensagens (id INTEGER PRIMARY KEY, telefone TEXT NOT NULL REFERENCES "
        "contatos(telefone), quando REAL NOT NULL, quem TEXT NOT NULL, texto TEXT NOT NULL)",
        "CREATE INDEX mensagens_contato ON mensagens(telefone, id)",
        "CREATE TABLE pausados (telefone TEXT PRIMARY KEY, nome TEXT, motivo TEXT, desde REAL)",
        "CREATE TABLE ligacoes (id INTEGER PRIMARY KEY, telefone TEXT, quando REAL, "
        "duracao REAL, desfecho TEXT)",
        "CREATE TABLE eventos (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, "
        "quando REAL, dados TEXT)",
        "CREATE TABLE importados (arquivo TEXT PRIMARY KEY)",
        "CREATE VIRTUAL TABLE busca USING fts5(texto, content='mensagens', content_rowid='id')",
        "CREATE TRIGGER mensagens_inserir AFTER INSERT ON mensagens BEGIN "
        "INSERT INTO busca(rowid, texto) VALUES (new.id, new.texto); END",
        "CREATE TRIGGER mensagens_apagar AFTER DELETE ON mensagens BEGIN "
        "INSERT INTO busca(busca, rowid, texto) VALUES ('delete', old.id, old.texto); END",
    ):
        db.execute(sql)


class RegistrosAtendimento:
    def __init__(self, pasta: Path, turnos: int = 20) -> None:
        self.pasta = pasta
        self.turnos = turnos
        self.banco = Banco(pasta / "atendimento.db", (_esquema,))
        self._importar()

    def _importar(self) -> None:
        arquivos = sorted((self.pasta / "conversas").glob("*.jsonl"))
        if (self.pasta / "pausados.json").is_file():
            arquivos.append(self.pasta / "pausados.json")
        for arquivo in arquivos:
            chave = str(arquivo.relative_to(self.pasta))
            with self.banco.conexao() as db:
                db.execute("BEGIN IMMEDIATE")
                if not db.execute("SELECT 1 FROM importados WHERE arquivo=?", (chave,)).fetchone():
                    # Um arquivo inválido fica no lugar e a transação não importa só uma parte.
                    if arquivo.suffix == ".jsonl":
                        telefone = arquivo.stem
                        db.execute("INSERT OR IGNORE INTO contatos VALUES (?)", (telefone,))
                        for linha in arquivo.read_text().splitlines():
                            if not linha.strip():
                                continue
                            dado = json.loads(linha)
                            db.execute(
                                "INSERT INTO mensagens(telefone, quando, quem, texto) "
                                "VALUES (?, ?, ?, ?)",
                                (telefone, dado.get("quando", 0), dado["quem"], dado["texto"]),
                            )
                    else:
                        for telefone, dado in json.loads(arquivo.read_text()).items():
                            db.execute(
                                "INSERT OR IGNORE INTO pausados VALUES (?, ?, ?, ?)",
                                (telefone, dado["nome"], dado["motivo"], dado["desde"]),
                            )
                    db.execute("INSERT INTO importados VALUES (?)", (chave,))
            # Só arquiva depois do commit. Se cair aqui, a marca evita duplicar ao retomar.
            destino = self.pasta.parent / ".antes-do-sqlite" / self.pasta.name / chave
            destino.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if arquivo.exists():
                arquivo.chmod(0o600)
                arquivo.replace(destino)

    def historico(self, telefone: str) -> list[dict[str, str]]:
        with self.banco.conexao() as db:
            linhas = db.execute(
                "SELECT quando, quem, texto FROM mensagens WHERE telefone=? "
                "ORDER BY id DESC LIMIT ?",
                (telefone, self.turnos),
            ).fetchall()
        return [dict(linha) for linha in reversed(linhas)]

    def anotar(self, telefone: str, quem: str, texto: str) -> None:
        with self.banco.conexao() as db:
            db.execute("INSERT OR IGNORE INTO contatos VALUES (?)", (telefone,))
            db.execute(
                "INSERT INTO mensagens(telefone, quando, quem, texto) VALUES (?, ?, ?, ?)",
                (telefone, time.time(), quem, texto),
            )

    def memoria(self) -> dict[str, Any]:
        with self.banco.conexao() as db:
            linha = db.execute(
                "SELECT (SELECT count(*) FROM contatos) AS contatos, "
                "(SELECT count(*) FROM mensagens) AS mensagens"
            ).fetchone()
        return {**dict(linha), "lembra": self.turnos}

    def esquecer(self) -> int:
        with self.banco.conexao() as db:
            db.execute("BEGIN IMMEDIATE")
            quantidade = int(db.execute("SELECT count(*) FROM contatos").fetchone()[0])
            db.execute("DELETE FROM mensagens")
            db.execute("DELETE FROM contatos")
        return quantidade

    def pausados(self) -> list[dict[str, Any]]:
        with self.banco.conexao() as db:
            return [dict(linha) for linha in db.execute("SELECT * FROM pausados ORDER BY rowid")]

    def pausado(self, telefone: str) -> bool:
        with self.banco.conexao() as db:
            return (
                db.execute("SELECT 1 FROM pausados WHERE telefone=?", (telefone,)).fetchone()
                is not None
            )

    def pausar(self, telefone: str, nome: str, motivo: str) -> None:
        with self.banco.conexao() as db:
            db.execute(
                "INSERT INTO pausados VALUES (?, ?, ?, ?) ON CONFLICT(telefone) "
                "DO UPDATE SET nome=excluded.nome, motivo=excluded.motivo, desde=excluded.desde",
                (telefone, nome, motivo, time.time()),
            )

    def devolver(self, telefone: str) -> bool:
        with self.banco.conexao() as db:
            return db.execute("DELETE FROM pausados WHERE telefone=?", (telefone,)).rowcount > 0

    def buscar(self, texto: str, limite: int = 50) -> list[dict[str, Any]]:
        # A consulta é uma frase literal: caracteres do usuário não viram operadores FTS.
        consulta = '"' + texto.replace('"', '""') + '"'
        with self.banco.conexao() as db:
            return [
                dict(linha)
                for linha in db.execute(
                    "SELECT mensagens.* FROM busca JOIN mensagens ON mensagens.id=busca.rowid "
                    "WHERE busca MATCH ? ORDER BY rank LIMIT ?",
                    (consulta, limite),
                )
            ]

    def ligacao(self, telefone: str, desfecho: str, duracao: float) -> None:
        with self.banco.conexao() as db:
            db.execute(
                "INSERT INTO ligacoes(telefone, quando, duracao, desfecho) VALUES (?, ?, ?, ?)",
                (telefone, time.time(), duracao, desfecho),
            )

    def publicar_evento(self, tipo: str, dados: dict[str, Any], tamanho: int) -> None:
        with self.banco.conexao() as db:
            db.execute(
                "INSERT INTO eventos(tipo, quando, dados) VALUES (?, ?, ?)",
                (tipo, time.time(), json.dumps(dados, ensure_ascii=False)),
            )
            db.execute(
                "DELETE FROM eventos WHERE id <= (SELECT max(id) FROM eventos)-?", (tamanho,)
            )

    def eventos(self, visto: int) -> tuple[list[dict[str, Any]], int]:
        with self.banco.conexao() as db:
            ultimo = (
                int(
                    db.execute("SELECT seq FROM sqlite_sequence WHERE name='eventos'").fetchone()[0]
                )
                if db.execute("SELECT 1 FROM sqlite_sequence WHERE name='eventos'").fetchone()
                else 0
            )
            if visto > ultimo:
                visto = 0
            linhas = db.execute("SELECT * FROM eventos WHERE id>? ORDER BY id", (visto,)).fetchall()
        return [
            {"id": x["id"], "tipo": x["tipo"], "quando": x["quando"], **json.loads(x["dados"])}
            for x in linhas
        ], ultimo
