"""As pesquisas guardadas do Zé (ADR 0060): cada pesquisa feita vira um registro que se consulta
no painel (página Pesquisas) e que o Zé reabre pela voz ("o que achamos sobre embalagens?"),
sem pesquisar de novo.

Um JSON por pesquisa em `DADOS/pesquisas/`: a pergunta, quando, as consultas, as fontes com os
trechos lidos e o resto do que a busca achou; ou, na pesquisa resumida (`internet_pesquisar`, ou a
reserva da profunda), o resumo com as fontes. Fica no computador, para sempre, até apagar.
"""

import asyncio
import json
import logging
import re
import secrets
import threading
import time
import unicodedata
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from zervis import lugares

log = logging.getLogger(__name__)

PASTA = lugares.DADOS / "pesquisas"
ID = re.compile(r"\d{8}-\d{6}-[0-9a-f]{6}")
LISTA_MAX = 200


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )


def _palavras(texto: str) -> list[str]:
    return [p for p in re.findall(r"\w+", _sem_acento(texto)) if len(p) >= 3 or p.isdigit()]


def _texto_todo(p: dict[str, Any]) -> str:
    partes = [p.get("pergunta", ""), " ".join(p.get("consultas") or []), p.get("resumo", "")]
    for f in p.get("fontes") or []:
        partes += [f.get("titulo", ""), f.get("site", ""), " ".join(f.get("trechos") or [])]
    return " ".join(str(x) for x in partes)


def resumo(p: dict[str, Any]) -> dict[str, Any]:
    """O que a lista mostra de cada pesquisa."""
    fontes = p.get("fontes") or []
    sites = list(dict.fromkeys(f.get("site", "") for f in fontes if f.get("site")))
    return {
        "id": p["id"],
        "pergunta": p.get("pergunta", ""),
        "em": p.get("em", 0),
        "tipo": p.get("tipo", "profunda"),
        "fontes": len(fontes) or len(re.findall(r"https?://", p.get("resumo", ""))),
        "sites": sites[:5],
    }


class Guardadas:
    def __init__(self, pasta: Path = PASTA, agora: Callable[[], float] = time.time) -> None:
        self.pasta = pasta
        self.agora = agora
        self._trava = threading.Lock()

    def gravar(self, pesquisa: dict[str, Any]) -> str:
        """Guarda e devolve o id (vazio se o disco falhar: a pesquisa em si não pode cair)."""
        em = self.agora()
        id_ = time.strftime("%Y%m%d-%H%M%S-", time.localtime(em)) + secrets.token_hex(3)
        registro = {"id": id_, "em": em, "tipo": "profunda", **pesquisa}
        try:
            with self._trava:
                self.pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
                (self.pasta / f"{id_}.json").write_text(json.dumps(registro, ensure_ascii=False))
        except OSError as erro:
            log.warning("pesquisa não guardada: %s", erro)
            return ""
        return id_

    def _todas(self) -> list[dict[str, Any]]:
        saida = []
        for arquivo in (
            sorted(self.pasta.glob("*.json"), reverse=True) if self.pasta.is_dir() else []
        ):
            if not ID.fullmatch(arquivo.stem):
                continue
            try:
                dados = json.loads(arquivo.read_text())
            except (OSError, ValueError):
                continue
            if isinstance(dados, dict) and dados.get("id") == arquivo.stem:
                saida.append(dados)
        return saida

    def listar(self, busca: str = "", quantas: int = LISTA_MAX) -> list[dict[str, Any]]:
        """As mais novas primeiro; com `busca`, as que têm mais palavras dela (sem acento)."""
        todas = self._todas()
        procuradas = set(_palavras(busca))
        if not procuradas:
            return [resumo(p) for p in todas[:quantas]]
        notas = []
        for p in todas:
            palavras = set(_palavras(_texto_todo(p)))
            achadas = procuradas & palavras
            if not achadas:
                continue
            na_pergunta = procuradas & set(_palavras(p.get("pergunta", "")))
            notas.append((len(achadas) + 0.5 * len(na_pergunta), p.get("em", 0), p))
        notas.sort(key=lambda n: (-n[0], -n[1]))
        return [resumo(p) for _, _, p in notas[:quantas]]

    def ler(self, id_: str) -> dict[str, Any]:
        if not ID.fullmatch(id_ or ""):
            raise ValueError("pesquisa inválida")
        try:
            dados = json.loads((self.pasta / f"{id_}.json").read_text())
        except (OSError, ValueError):
            raise ValueError("essa pesquisa não existe mais") from None
        if not isinstance(dados, dict):
            raise ValueError("essa pesquisa não existe mais")
        return dados

    def apagar(self, id_: str) -> None:
        self.ler(id_)  # confere o id e que existe
        (self.pasta / f"{id_}.json").unlink(missing_ok=True)


def guardando(
    pesquisar: Callable[[str], Awaitable[str]], guardadas: Guardadas
) -> Callable[[str], Awaitable[str]]:
    """A pesquisa resumida (`internet_pesquisar` e a reserva da profunda) também fica guardada."""

    async def pesquisar_e_guardar(pedido: str) -> str:
        texto = await pesquisar(pedido)
        await asyncio.to_thread(
            guardadas.gravar, {"tipo": "resumida", "pergunta": pedido, "resumo": texto}
        )
        return texto

    return pesquisar_e_guardar


def quando(em: float) -> str:
    return time.strftime("%d/%m/%Y %H:%M", time.localtime(em))
