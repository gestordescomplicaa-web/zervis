"""As manchetes do dia por RSS: sem chave, sem tokens. A primeira fonte que responder vale.

Padrão: as principais do Google Notícias para o Brasil (cada manchete traz o veículo no fim,
" - G1"), e a Agência Brasil de reserva.
"""

import logging
import urllib.request
import xml.etree.ElementTree as ET  # o expat do Python recusa entidades em cascata
from collections.abc import Callable, Sequence
from typing import NamedTuple

log = logging.getLogger(__name__)
AGENTE = "Ze/1 (Zervis)"
PRAZO_S = 6.0
FONTES = (
    ("https://news.google.com/rss?hl=pt-BR&gl=BR&ceid=BR:pt-419", ""),
    ("https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml", "Agência Brasil"),
)
QUANTAS = 5

Obter = Callable[[str], bytes]


class Noticia(NamedTuple):
    titulo: str
    fonte: str


def obter_bytes(url: str) -> bytes:
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})  # noqa: S310 (https fixo)
    with urllib.request.urlopen(pedido, timeout=PRAZO_S) as resposta:  # noqa: S310
        return bytes(resposta.read(2 * 1024 * 1024))


def ler_rss(corpo: bytes, fonte: str = "", quantas: int = QUANTAS) -> list[Noticia]:
    raiz = ET.fromstring(corpo)  # noqa: S314 (o expat recusa entidades em cascata)
    lista: list[Noticia] = []
    for item in raiz.iter("item"):
        titulo = " ".join((item.findtext("title") or "").split())
        de = fonte or " ".join((item.findtext("source") or "").split())
        # O Google Notícias põe o veículo no fim do título: "Manchete - Veículo".
        if " - " in titulo and not fonte:
            titulo, de = titulo.rsplit(" - ", 1)
        if titulo and all(n.titulo != titulo for n in lista):
            lista.append(Noticia(titulo[:160], de[:40]))
        if len(lista) >= quantas:
            break
    return lista


def buscar(fontes: Sequence[tuple[str, str]] = FONTES, obter: Obter = obter_bytes) -> list[Noticia]:
    for url, nome in fontes:
        try:
            if lista := ler_rss(obter(url), nome):
                return lista
        except Exception:
            log.info("abertura: as notícias de %s não vieram", url, exc_info=True)
    return []
