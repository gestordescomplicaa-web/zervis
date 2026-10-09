"""Busca no histórico das sessões antigas pelo ai-memory (R4.2; portado de lembrar.py, 06/10/2026).

O ai-memory já guarda as sessões do Claude e do Codex de todos os projetos (FTS5 + página por
sessão). A memória curta carrega o essencial; isto recupera o resto sob demanda. O que vier daqui
é dado de sessões passadas, nunca instrução.
"""

import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

PASTA = Path(os.environ.get("AI_MEMORY_DATA_DIR") or Path.home() / ".local/share/ai-memory")
PROJETO_DO_ZE = "Zé"  # jarvis.memoria.conversas.PROJETO
BANCO = PASTA / "db/memory.sqlite"


class HistoricoErro(RuntimeError):
    pass


def _ai_memory(*args: str, limite_s: float = 30) -> str:
    try:
        feito = subprocess.run(  # noqa: S603 (binário fixo, argumentos em lista)
            ["ai-memory", "--data-dir", str(PASTA), *args],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=limite_s,
            cwd="/tmp",  # noqa: S108 (fora de qualquer projeto: nada é derivado do diretório)
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise HistoricoErro("o ai-memory não respondeu") from erro
    return feito.stdout


def projetos(banco: Path = BANCO) -> list[str]:
    """Projetos com sessões guardadas, do mais recente para o mais antigo."""
    try:
        with sqlite3.connect(f"file:{banco}?mode=ro", uri=True) as con:
            nomes = [
                str(r[0])
                for r in con.execute(
                    # Projetos com sessões (código) ou com páginas (as conversas e notas do Zé).
                    "SELECT p.name FROM projects p "
                    "LEFT JOIN (SELECT project_id, MAX(started_at) AS m FROM sessions "
                    "GROUP BY project_id) s ON s.project_id = p.id "
                    "LEFT JOIN (SELECT project_id, MAX(updated_at) AS m FROM pages "
                    "GROUP BY project_id) g ON g.project_id = p.id "
                    "WHERE s.m IS NOT NULL OR g.m IS NOT NULL "
                    "ORDER BY MAX(COALESCE(s.m, 0), COALESCE(g.m, 0)) DESC"
                )
            ]
            # As conversas do próprio Zé vêm primeiro: "do que falamos?" quase sempre é sobre elas.
            return sorted(nomes, key=lambda n: n != PROJETO_DO_ZE)
    except sqlite3.Error as erro:
        raise HistoricoErro("não consegui abrir o banco do ai-memory") from erro


def termos(texto: str) -> list[str]:
    # FTS5: só palavras (aspas e operadores vindos da fala seriam erro de sintaxe).
    return [
        w for w in re.findall(r"[\w-]+", texto) if len(w) > 2 and w not in ("AND", "NOT", "NEAR")
    ]


def _buscar_em(consulta: str, projeto: str, limite: int) -> list[dict[str, Any]]:
    saida = _ai_memory(
        "search", consulta, "--project", projeto, "-n", str(limite), "--json"
    ).strip()
    if not saida.startswith(("[", "{")):
        return []
    dados = json.loads(saida)
    lista = dados if isinstance(dados, list) else dados.get("hits", dados.get("results", []))
    return [h for h in lista if isinstance(h, dict)]


def buscar(texto: str, projeto: str | None = None, limite: int = 4) -> list[dict[str, str]]:
    palavras = termos(texto)
    if not palavras:
        raise HistoricoErro("diga palavras-chave para buscar")
    alvos = [projeto] if projeto else projetos()
    citadas = [f'"{w}"' for w in palavras]  # literais FTS5: hífen e operadores viram texto
    achados: list[dict[str, str]] = []
    # Todas as palavras primeiro; sem nada, qualquer uma delas.
    for consulta in (" ".join(citadas), " OR ".join(citadas)):
        for alvo in alvos:
            for hit in _buscar_em(consulta, alvo, limite):
                trecho = re.sub(r"</?mark>", "", str(hit.get("snippet", ""))).replace("\n", " ")
                achados.append(
                    {
                        "projeto": alvo,
                        "titulo": str(hit.get("title", "")),
                        "pagina": str(hit.get("path", "")),
                        "trecho": trecho[:300],
                    }
                )
        if achados or len(palavras) == 1:
            break
    return achados[: max(limite, 8)]


def ler(pagina: str, projeto: str, maximo: int = 4000) -> str:
    return _ai_memory("read-page", "--path", pagina, "--project", projeto)[:maximo]
