"""A pesquisa profunda do Zé (ADR 0059): buscar de vários jeitos, abrir as melhores páginas e
trazer os trechos que respondem, com a fonte de cada um.

Diferente do `internet_pesquisar` (um resumo pronto, feito por outro modelo), aqui o cérebro recebe
o material: as consultas rodam juntas no SearXNG do Zé, os resultados se juntam (o mesmo endereço
achado por mais de uma consulta ou buscador sobe), no máximo duas páginas por site, e as primeiras
são lidas ao mesmo tempo pelo leitor. De cada página vão os trechos com mais palavras da pergunta,
escolhidos aqui, sem gastar token; a leitura inteira fica guardada para continuar com
`navegador_continuar`. O relatório vai para `DADOS/pesquisas/`.

Para empresas, mercado, concorrentes, fornecedores e figuras públicas. Dossiê de pessoa comum,
não (regra da persona).
"""

import concurrent.futures
import logging
import re
import time
import unicodedata
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from zervis import lugares
from zervis.cerebro import navegador
from zervis.pesquisa import leitor
from zervis.pesquisa.buscador import BuscadorErro, Resultado

log = logging.getLogger(__name__)

PASTA = lugares.DADOS / "pesquisas"
CONSULTAS_MAX = 4
PAGINAS = 5
POR_SITE = 2
TRECHOS = 3
TRECHO_MAX = 700
LER_S = 50.0  # o teto para ler as páginas, todas juntas
RASTREIO = re.compile(r"^(utm_\w+|fbclid|gclid|mc_\w+|ref|ref_src)$", re.IGNORECASE)
VAZIAS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos", "e", "em", "é", "na",
    "nas", "no", "nos", "o", "os", "ou", "para", "pela", "pelas", "pelo", "pelos", "por", "qual",
    "quais", "que", "quem", "se", "sem", "sobre", "um", "uma", "uns", "umas", "the", "of", "and",
    "for", "in", "on", "to", "is", "what", "who", "how",
}  # fmt: skip


class ProfundaErro(RuntimeError):
    pass


class Busca(Protocol):
    """A tomada do buscador: hoje o SearXNG (`buscador.Buscador`)."""

    def buscar(self, consulta: str) -> list[Resultado]: ...


@dataclass
class Fonte:
    n: int
    titulo: str
    url: str
    site: str = ""
    data: str = ""
    trechos: list[str] = field(default_factory=list)
    leitura: str = ""
    por: str = ""


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )


def termos(texto: str) -> set[str]:
    """As palavras que contam numa pergunta: sem acento, sem as vazias, com 3 letras ou número."""
    return {
        p
        for p in re.findall(r"\w+", _sem_acento(texto))
        if p not in VAZIAS and (len(p) >= 3 or p.isdigit())
    }


def chave(url: str) -> str:
    """O mesmo endereço escrito de jeitos diferentes vira uma chave só."""
    partes = urllib.parse.urlsplit(url)
    host = (partes.hostname or "").removeprefix("www.")
    query = urllib.parse.urlencode(
        [(k, v) for k, v in urllib.parse.parse_qsl(partes.query) if not RASTREIO.match(k)]
    )
    return f"{host}{partes.path.rstrip('/')}" + (f"?{query}" if query else "")


def site(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").removeprefix("www.")


def juntar(listas: list[list[Resultado]]) -> list[Resultado]:
    """Os resultados de todas as consultas numa lista só, sem repetir endereço. Sobe quem aparece
    alto em mais consultas (fusão por posição, a RRF) e em mais buscadores."""
    pontos: dict[str, float] = {}
    primeiro: dict[str, Resultado] = {}
    for lista in listas:
        for posicao, r in enumerate(lista):
            k = chave(r.url)
            primeiro.setdefault(k, r)
            pontos[k] = pontos.get(k, 0.0) + 1 / (60 + posicao) + 0.002 * len(r.motores)
    return [primeiro[k] for k in sorted(pontos, key=lambda k: -pontos[k])]


def trechos(texto: str, procurados: set[str], quantos: int = TRECHOS) -> list[str]:
    """Os pedaços da página com mais palavras da pergunta, na ordem em que aparecem."""
    blocos: list[str] = []
    atual = ""
    for linha in (x.strip() for x in texto.split("\n")):
        if not linha:
            continue
        if atual and len(atual) + len(linha) > TRECHO_MAX:
            blocos.append(atual)
            atual = ""
        atual = f"{atual} {linha}".strip()
    if atual:
        blocos.append(atual)
    notas = []
    for i, bloco in enumerate(blocos):
        palavras = re.findall(r"\w+", _sem_acento(bloco))
        achadas = procurados.intersection(palavras)
        if achadas:
            vezes = sum(1 for p in palavras if p in procurados)
            notas.append((len(achadas) + 0.05 * min(vezes, 20), i))
    melhores = sorted(i for _, i in sorted(notas, reverse=True)[:quantos])
    escolhidos = [blocos[i] for i in melhores] or blocos[:1]
    return [b[:TRECHO_MAX] + ("…" if len(b) > TRECHO_MAX else "") for b in escolhidos]


def _buscar_todas(buscador: Busca, consultas: list[str]) -> list[list[Resultado]]:
    with concurrent.futures.ThreadPoolExecutor(len(consultas)) as ex:
        futuros = [ex.submit(buscador.buscar, c) for c in consultas]
    listas, falhas = [], []
    for f in futuros:
        try:
            listas.append(f.result())
        except BuscadorErro as erro:
            falhas.append(str(erro))
    if not listas:
        raise ProfundaErro(falhas[0] if falhas else "o buscador não respondeu")
    return listas


def _ler_varias(
    candidatos: list[Resultado], quantas: int, ler: Callable[[str], leitor.Pagina]
) -> list[tuple[Resultado, leitor.Pagina]]:
    """Lê as candidatas ao mesmo tempo; fica com as `quantas` primeiras (pela ordem da busca)
    que abriram dentro do teto de tempo."""
    ex = concurrent.futures.ThreadPoolExecutor(min(8, len(candidatos)) or 1)
    futuros = [ex.submit(ler, r.url) for r in candidatos]
    concurrent.futures.wait(futuros, timeout=LER_S)
    ex.shutdown(wait=False, cancel_futures=True)
    lidas = []
    for r, f in zip(candidatos, futuros, strict=True):
        if f.done() and not f.cancelled() and f.exception() is None:
            lidas.append((r, f.result()))
        elif f.done() and not f.cancelled():
            log.info("profunda: não li %s (%s)", r.url, f.exception())
    return lidas[:quantas]


def _relatorio(pergunta: str, fontes: list[Fonte], pasta: Path) -> str:
    nome = time.strftime("%Y-%m-%d-%H%M%S-") + re.sub(r"\W+", "-", _sem_acento(pergunta))[:50]
    linhas = [f"# {pergunta}", "", time.strftime("Pesquisado em %d/%m/%Y %H:%M."), ""]
    for f in fontes:
        linhas += [f"## [{f.n}] {f.titulo or f.site}", f.url, ""]
        linhas += [f"> {t}\n" for t in f.trechos]
    try:
        pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        (pasta / f"{nome.strip('-')}.md").write_text("\n".join(linhas))
    except OSError as erro:
        log.warning("profunda: relatório não gravado (%s)", erro)
        return ""
    return f"{nome.strip('-')}.md"


def pesquisar(
    pergunta: str,
    consultas: list[str],
    buscador: Busca,
    paginas: int = PAGINAS,
    ler: Callable[[str], leitor.Pagina] = leitor.ler,
    pasta: Path = PASTA,
    guardar: Callable[[str], str] = navegador.guardar,
) -> dict[str, Any]:
    """As fontes lidas, cada uma com os trechos que respondem, e o resto do que a busca achou."""
    vistas: set[str] = set()
    lista = []
    for c in [*consultas, pergunta]:
        c = " ".join(str(c).split())[:200]
        if c and c.lower() not in vistas:
            vistas.add(c.lower())
            lista.append(c)
    achados = juntar(_buscar_todas(buscador, lista[:CONSULTAS_MAX]))
    if not achados:
        raise ProfundaErro("a busca não achou nada")
    por_site: dict[str, int] = {}
    candidatos = []
    for r in achados:
        if por_site.get(site(r.url), 0) < POR_SITE:
            por_site[site(r.url)] = por_site.get(site(r.url), 0) + 1
            candidatos.append(r)
    paginas = max(1, min(paginas, 8))
    lidas = _ler_varias(candidatos[: paginas + 2], paginas, ler)
    procurados = termos(" ".join([pergunta, *consultas]))
    fontes = [
        Fonte(
            n=n,
            titulo=p.titulo or r.titulo,
            url=p.url,
            site=p.site or site(p.url),
            data=p.data or r.data,
            trechos=trechos(p.texto, procurados),
            leitura=guardar(p.texto),
            por=p.por,
        )
        for n, (r, p) in enumerate(lidas, start=1)
    ]
    usados = {chave(f.url) for f in fontes} | {chave(r.url) for r, _ in lidas}
    outros = [
        {"titulo": r.titulo, "url": r.url, "trecho": r.trecho}
        for r in achados
        if chave(r.url) not in usados
    ][:8]
    return {
        "pergunta": pergunta,
        "consultas": lista[:CONSULTAS_MAX],
        "fontes": [{k: v for k, v in f.__dict__.items() if v} for f in fontes],
        "outros_resultados": outros,
        "relatorio": _relatorio(pergunta, fontes, pasta),
    }
