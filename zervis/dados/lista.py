"""Uma lista de registros em SQLite, no lugar de um arquivo JSON regravado inteiro.

Plano de maturidade, Frente 1 ("estado só em SQLite"): avisos, pendências, leads, a lista de
prioridade e as ligações eram listas JSON trocadas por um arquivo temporário a cada mudança.
Duas instâncias (ou dois processos) que leem e regravam ao mesmo tempo perdiam a escrita de uma
delas, e um arquivo cortado no meio virava lista vazia. Aqui a lista fica num banco próprio
(`<arquivo>.db`, 0600, WAL), lida e regravada dentro de uma transação; o JSON de antes é
importado uma vez e guardado em `.antes-do-sqlite/`.

Fica em arquivo, de propósito: a configuração que a pessoa edita (`<config>/*.json`) e o
`status.json` de 1 Hz, que scripts leem por fora.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from zervis.dados.documentos import Documentos


class Lista:
    def __init__(self, arquivo: Path, colecao: str, campo_chave: str = "id") -> None:
        self.colecao = colecao
        self.campo_chave = campo_chave
        self._dados = Documentos(arquivo)
        self.arquivo = self._dados.banco.arquivo
        self._dados.importar(arquivo, self._antiga, colecao, campo_chave=campo_chave)

    def _antiga(self, texto: str) -> list[dict[str, Any]]:
        """O JSON de antes, tolerante: um arquivo cortado ou um item sem chave não impedem o
        Zé de subir (o arquivo fica guardado ao lado, para conferir)."""
        try:
            brutos = json.loads(texto)
        except ValueError:
            return []
        if not isinstance(brutos, list):
            return []
        return [dict(b) for b in brutos if isinstance(b, dict) and b.get(self.campo_chave)]

    @contextmanager
    def transacao(self) -> Iterator[None]:
        """Ler e regravar dentro dela: ninguém escreve no meio (nem outro processo)."""
        with self._dados.banco.transacao():
            yield

    def ler(self) -> list[dict[str, Any]]:
        return self._dados.listar(self.colecao)

    def gravar(self, itens: list[dict[str, Any]]) -> None:
        self._dados.substituir(self.colecao, itens, self.campo_chave)
