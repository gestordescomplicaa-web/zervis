"""Coleções de registros JSON em SQLite: ordenação, FTS e importação recuperável."""

import json
import sqlite3
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from zervis.dados import Banco


def esquema(db: sqlite3.Connection) -> None:
    for sql in (
        "CREATE TABLE registros (id INTEGER PRIMARY KEY AUTOINCREMENT, colecao TEXT NOT NULL, "
        "chave TEXT NOT NULL, dados TEXT NOT NULL, texto TEXT NOT NULL, UNIQUE(colecao, chave))",
        "CREATE INDEX registros_colecao ON registros(colecao, id)",
        "CREATE TABLE importados (arquivo TEXT PRIMARY KEY)",
        "CREATE VIRTUAL TABLE busca USING fts5(texto, content='registros', content_rowid='id')",
        "CREATE TRIGGER inserir AFTER INSERT ON registros BEGIN "
        "INSERT INTO busca(rowid,texto) VALUES(new.id,new.texto); END",
        "CREATE TRIGGER apagar AFTER DELETE ON registros BEGIN "
        "INSERT INTO busca(busca,rowid,texto) VALUES('delete',old.id,old.texto); END",
        "CREATE TRIGGER atualizar AFTER UPDATE ON registros BEGIN "
        "INSERT INTO busca(busca,rowid,texto) VALUES('delete',old.id,old.texto); "
        "INSERT INTO busca(rowid,texto) VALUES(new.id,new.texto); END",
    ):
        db.execute(sql)


class Documentos:
    def __init__(self, arquivo: Path) -> None:
        self.banco = Banco(arquivo.with_suffix(".db"), (esquema,))

    def guardar(self, colecao: str, dados: dict[str, Any], chave: str = "") -> None:
        texto = json.dumps(dados, ensure_ascii=False)
        with self.banco.conexao() as db:
            db.execute(
                "INSERT INTO registros(colecao,chave,dados,texto) VALUES (?,?,?,?) "
                "ON CONFLICT(colecao,chave) DO UPDATE "
                "SET dados=excluded.dados, texto=excluded.texto",
                (colecao, chave or uuid.uuid4().hex, texto, texto),
            )

    def ler(self, colecao: str, chave: str) -> dict[str, Any] | None:
        with self.banco.conexao() as db:
            linha = db.execute(
                "SELECT dados FROM registros WHERE colecao=? AND chave=?", (colecao, chave)
            ).fetchone()
        return dict(json.loads(linha[0])) if linha else None

    def listar(
        self, colecao: str, limite: int = -1, desde: int = 0, reverso: bool = False
    ) -> list[dict[str, Any]]:
        sql = (
            "SELECT dados FROM registros WHERE colecao=? ORDER BY id DESC LIMIT ? OFFSET ?"
            if reverso
            else "SELECT dados FROM registros WHERE colecao=? ORDER BY id ASC LIMIT ? OFFSET ?"
        )
        with self.banco.conexao() as db:
            linhas = db.execute(
                sql,
                (colecao, limite, max(0, desde)),
            ).fetchall()
        return [dict(json.loads(linha[0])) for linha in linhas]

    def filtrar(
        self, colecao: str, campo: str, valores: list[str], limite: int
    ) -> list[dict[str, Any]]:
        if not valores:
            return []
        with self.banco.conexao() as db:
            linhas = db.execute(
                "SELECT dados FROM registros WHERE colecao=? AND json_extract(dados,?) "
                "IN (SELECT value FROM json_each(?)) ORDER BY id DESC LIMIT ?",
                (colecao, "$." + campo, json.dumps(valores), limite),
            ).fetchall()
        return [dict(json.loads(linha[0])) for linha in linhas]

    def remover(self, colecao: str, chave: str | None = None) -> None:
        with self.banco.conexao() as db:
            if chave is None:
                db.execute("DELETE FROM registros WHERE colecao=?", (colecao,))
            else:
                db.execute("DELETE FROM registros WHERE colecao=? AND chave=?", (colecao, chave))

    def substituir(self, colecao: str, dados: list[dict[str, Any]], campo_chave: str) -> None:
        with self.banco.transacao():
            self.remover(colecao)
            for item in dados:
                self.guardar(colecao, item, str(item[campo_chave]))

    def buscar(self, texto: str, colecao: str, limite: int = 50) -> list[dict[str, Any]]:
        consulta = '"' + texto.replace('"', '""') + '"'
        with self.banco.conexao() as db:
            linhas = db.execute(
                "SELECT dados FROM busca JOIN registros ON registros.id=busca.rowid "
                "WHERE busca MATCH ? AND colecao=? ORDER BY rank LIMIT ?",
                (consulta, colecao, limite),
            ).fetchall()
        return [dict(json.loads(linha[0])) for linha in linhas]

    def importar(
        self,
        arquivo: Path,
        ler: Callable[[str], list[dict[str, Any]]],
        colecao: str,
        chave: str = "",
        campo_chave: str = "",
    ) -> None:
        if not arquivo.is_file() or arquivo == self.banco.arquivo:
            return
        marca = str(arquivo.resolve())
        with self.banco.transacao() as db:
            if not db.execute("SELECT 1 FROM importados WHERE arquivo=?", (marca,)).fetchone():
                for indice, item in enumerate(ler(arquivo.read_text())):
                    identificador = (
                        str(item[campo_chave]) if campo_chave else chave or f"{marca}:{indice}"
                    )
                    self.guardar(colecao, item, identificador)
                db.execute("INSERT INTO importados VALUES (?)", (marca,))
        destino = arquivo.parent / ".antes-do-sqlite" / arquivo.name
        destino.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if arquivo.exists():
            arquivo.chmod(0o600)
            arquivo.replace(destino)


def linhas_json(texto: str) -> list[dict[str, Any]]:
    return [dict(json.loads(linha)) for linha in texto.splitlines() if linha.strip()]


def lista_json(texto: str) -> list[dict[str, Any]]:
    return [dict(item) for item in json.loads(texto)]


def objeto_json(texto: str) -> list[dict[str, Any]]:
    return [dict(json.loads(texto))]
