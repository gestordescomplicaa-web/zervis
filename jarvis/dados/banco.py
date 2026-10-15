"""SQLite compartilhado por processos, com migrações serializadas pelo próprio banco."""

import os
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

Migracao = Callable[[sqlite3.Connection], None]


class Banco:
    def __init__(self, arquivo: Path, migracoes: tuple[Migracao, ...] = ()) -> None:
        self.arquivo = arquivo
        self._local = threading.local()
        arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # O arquivo nasce privado; WAL e SHM herdam a permissão do banco.
        descritor = os.open(arquivo, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(descritor)
        arquivo.chmod(0o600)
        with self.conexao() as db:
            self._wal(db)
            db.execute("BEGIN IMMEDIATE")
            versao = int(db.execute("PRAGMA user_version").fetchone()[0])
            if versao > len(migracoes):
                raise ValueError("Banco criado por uma versão mais recente do Zérvis.")
            for indice, migrar in enumerate(migracoes[versao:], versao + 1):
                migrar(db)
                db.execute(f"PRAGMA user_version={indice}")

    @staticmethod
    def _wal(db: sqlite3.Connection) -> None:
        # A mudança inicial de journal não respeita busy_timeout em toda disputa de locks.
        fim = time.monotonic() + 30
        while True:
            try:
                if db.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
                    db.execute("PRAGMA journal_mode=WAL")
                return
            except sqlite3.OperationalError as erro:
                if (
                    erro.sqlite_errorcode & 0xFF not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
                    or time.monotonic() >= fim
                ):
                    raise
                time.sleep(0.02)

    @contextmanager
    def conexao(self) -> Iterator[sqlite3.Connection]:
        atual: sqlite3.Connection | None = getattr(self._local, "conexao", None)
        if atual is not None:
            yield atual
            return
        db = sqlite3.connect(self.arquivo, timeout=30)
        self._local.conexao = db
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=30000")
        try:
            with db:
                yield db
        finally:
            self._local.conexao = None
            db.close()

    @contextmanager
    def transacao(self) -> Iterator[sqlite3.Connection]:
        """Serializa leitura e alteração, inclusive quando os métodos internos se aninham."""
        with self.conexao() as db:
            if not db.in_transaction:
                db.execute("BEGIN IMMEDIATE")
            yield db

    def backup(self, destino: Path) -> None:
        """Cópia consistente inclusive enquanto outros processos escrevem no WAL."""
        if destino.resolve() == self.arquivo.resolve():
            raise ValueError("A cópia precisa de outro caminho.")
        destino.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descritor = os.open(destino, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(descritor)
        destino.chmod(0o600)
        with self.conexao() as origem, sqlite3.connect(destino) as copia:
            origem.backup(copia)
