"""A trava de temas (ADR 0125): os vídeos que o Zé faz sozinho não repetem assunto.

Cada roteiro diz o processo da empresa de que trata (atendimento, financeiro, fiscal, operação,
pessoas, gestão, pós-venda; `formatos.PROCESSOS`) e o assunto em poucas palavras ("proposta
comercial atrasada"). Os dois ficam num histórico (`<pasta dos vídeos>/temas.json`, os últimos
200), que sobrevive ao descarte do vídeo.

Quando o tema é livre (o agendado sem tema da lista nem artigo novo), o diretor recebe a lista
do que já foi feito e escolhe outro; e o roteiro volta a ele se repetir o processo de um dos
últimos vídeos ou um assunto parecido com um dos que já foram feitos (as palavras de peso em
comum). O tema que quem usa escreve não passa pela trava: foi pedido.
"""

import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

from zervis.video import formatos
from zervis.video.roteiro import RoteiroErro

ARQUIVO = "temas.json"
GUARDADOS = 200
NA_LISTA = 40  # os assuntos que o diretor vê
PROCESSO_SEGUIDO = 2  # o processo não repete nos últimos N vídeos de tema livre
PARECIDO = 0.5  # palavras de peso em comum (Jaccard) a partir das quais o assunto é o mesmo
_PALAVRA = re.compile(r"[a-z0-9]{4,}")
_VAZIAS = frozenset(
    {"para", "como", "mais", "sobre", "quem", "quando", "onde", "voce", "empresa", "empresas",
     "negocio", "negocios", "cliente", "clientes", "automacao", "automatica", "automatico",
     "automatizar"}
)  # fmt: skip


def _peso(texto: str) -> frozenset[str]:
    sem = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return frozenset(p for p in _PALAVRA.findall(sem) if p not in _VAZIAS)


def parecidos(a: str, b: str) -> bool:
    pa, pb = _peso(a), _peso(b)
    if not pa or not pb:
        return False
    return len(pa & pb) / len(pa | pb) >= PARECIDO


def historico(pasta: Path) -> list[dict[str, Any]]:
    """Do mais novo para o mais velho: o histórico gravado e, depois dele, os vídeos da pasta
    feitos antes da trava existir (pelo título, sem o processo)."""
    try:
        dados = json.loads((pasta / ARQUIVO).read_text())
    except (OSError, ValueError):
        dados = []
    itens = [x for x in dados if isinstance(x, dict)] if isinstance(dados, list) else []
    return itens + _antigos(pasta, {str(x.get("video")) for x in itens})


def _antigos(pasta: Path, conhecidos: set[str]) -> list[dict[str, Any]]:
    antigos = []
    for arquivo in pasta.glob("*/video.json") if pasta.is_dir() else []:
        try:
            v = json.loads(arquivo.read_text())
        except (OSError, ValueError):
            continue
        r = v.get("roteiro") if isinstance(v, dict) else None
        if not isinstance(r, dict) or str(v.get("id")) in conhecidos or not r.get("cenas"):
            continue
        assunto = str(r.get("assunto") or r.get("titulo") or v.get("tema") or "")
        if assunto:
            antigos.append({"video": str(v.get("id")), "processo": str(r.get("processo") or ""),
                            "assunto": assunto, "livre": False,
                            "quando": float(v.get("criado") or 0)})  # fmt: skip
    return sorted(antigos, key=lambda x: -x["quando"])


def anotar(pasta: Path, video: str, processo: str, assunto: str, livre: bool) -> None:
    try:
        gravados = json.loads((pasta / ARQUIVO).read_text())
    except (OSError, ValueError):
        gravados = []
    itens = [x for x in gravados if isinstance(x, dict) and x.get("video") != video]
    itens.insert(
        0,
        {"video": video, "processo": processo, "assunto": assunto, "livre": livre,
         "quando": time.time()},
    )  # fmt: skip
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / ARQUIVO).write_text(json.dumps(itens[:GUARDADOS], ensure_ascii=False, indent=1))


def secao(pasta: Path) -> str:
    """O que o diretor lê quando escolhe o tema: o que já foi feito e o processo a evitar."""
    itens = historico(pasta)
    if not itens:
        return ""
    feitos = "; ".join(f"{x.get('assunto')} ({x.get('processo')})" for x in itens[:NA_LISTA])
    evitar = {str(x.get("processo")) for x in itens[:PROCESSO_SEGUIDO] if x.get("processo")}
    outros = [k for k in formatos.PROCESSOS if k not in evitar]
    return (
        "## Temas já feitos (não repita)\n"
        f"Assuntos dos últimos vídeos: {feitos}.\n"
        f"Escolha um assunto novo, de um destes processos: {', '.join(outros)}.\n"
    )


def conferir(pasta: Path, processo: str, assunto: str, livre: bool) -> None:
    """Recusa o roteiro de tema livre que repete o processo recente ou um assunto já feito."""
    if not livre:
        return
    itens = historico(pasta)
    if processo and any(x.get("processo") == processo for x in itens[:PROCESSO_SEGUIDO]):
        raise RoteiroErro(
            f'O processo "{processo}" foi o tema de um dos últimos vídeos. Escolha outro processo.'
        )
    for x in itens:
        if assunto and parecidos(assunto, str(x.get("assunto", ""))):
            raise RoteiroErro(
                f'O assunto "{assunto}" já virou vídeo ("{x.get("assunto")}"). Escolha outro.'
            )
