"""As empresas de um ramo numa cidade, pelo Google Maps, com a Apify (ADR 0127).

O Google Maps é onde a empresa pequena do interior está (o LinkedIn, não). O ator
`compass/crawler-google-places` da Apify devolve nome, ramo, endereço, telefone, site, nota e as
avaliações; pedimos as piores, que são o sinal de dor (demora no atendimento, ninguém responde).
Custa por lugar achado, na conta de quem usa; a busca do Zé pede poucos por vez.

A chave fica em `<config>/apify.key` (0600), posta na página Prospecção, e vai no cabeçalho, nunca
no endereço (o endereço vai para log de proxy).
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from zervis import lugares

log = logging.getLogger(__name__)

ARQUIVO = lugares.CONFIG / "apify.key"
API = "https://api.apify.com/v2"
ATOR = "compass~crawler-google-places"
TEMPO_S = 300  # a busca síncrona espera o ator terminar
ESPERA_ATOR_S = 240  # o ator para antes do nosso tempo, e devolve o que achou
CONSOLE = "https://console.apify.com/settings/integrations"
RECLAMACOES = 3  # as piores avaliações com texto, por empresa
NOTA_RUIM = 3  # estrelas: até aqui, a avaliação é reclamação
_CHAVE = re.compile(r"[A-Za-z0-9_]{20,120}")

Abrir = Callable[[urllib.request.Request, float], Any]


class ApifyErro(RuntimeError):
    """Mensagem curta, pronta para a tela."""


@dataclass
class Lugar:
    id: str  # o placeId do Google: a mesma empresa achada de novo não entra duas vezes
    nome: str
    categoria: str = ""
    endereco: str = ""
    telefone: str = ""  # só dígitos, com o 55
    site: str = ""
    nota: float = 0.0
    avaliacoes: int = 0
    link: str = ""
    reclamacoes: list[str] = field(default_factory=list)

    def para_dados(self) -> dict[str, Any]:
        return asdict(self)


def chave(arquivo: Path = ARQUIVO) -> str:
    try:
        texto = arquivo.read_text().strip()
    except OSError:
        return ""
    return texto if _CHAVE.fullmatch(texto) else ""


def guardar(texto: str, arquivo: Path = ARQUIVO) -> None:
    """Confere a forma da chave e a guarda (0600); vazio a apaga."""
    texto = texto.strip()
    if not texto:
        arquivo.unlink(missing_ok=True)
        return
    if not _CHAVE.fullmatch(texto):
        raise ApifyErro("Chave inválida.")
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".tmp")
    temporario.write_text(texto)
    os.chmod(temporario, 0o600)
    temporario.replace(arquivo)


def _abrir(pedido: urllib.request.Request, tempo: float) -> Any:
    with urllib.request.urlopen(pedido, timeout=tempo) as r:  # noqa: S310 (só api.apify.com)
        return json.loads(r.read() or b"null")


def _pedido(caminho: str, chave_: str, corpo: Any = None) -> urllib.request.Request:
    dados = None if corpo is None else json.dumps(corpo).encode()
    return urllib.request.Request(  # noqa: S310 (sempre https://api.apify.com)
        f"{API}{caminho}",
        data=dados,
        method="GET" if corpo is None else "POST",
        headers={"Authorization": f"Bearer {chave_}", "Content-Type": "application/json"},
    )


def _chamar(pedido: urllib.request.Request, tempo: float, abrir: Abrir) -> Any:
    try:
        return abrir(pedido, tempo)
    except urllib.error.HTTPError as erro:
        if erro.code in (401, 403):
            raise ApifyErro("Chave inválida.") from None
        if erro.code == 402:
            raise ApifyErro("Sem crédito na Apify.") from None
        raise ApifyErro("A Apify recusou a busca.") from None
    except (urllib.error.URLError, OSError, ValueError):
        raise ApifyErro("Sem conexão com a Apify.") from None


def conferir(chave_: str, abrir: Abrir = _abrir) -> None:
    """A chave vale? (a conta dela; nada é cobrado)."""
    corpo = _chamar(_pedido("/users/me", chave_), 20, abrir)
    if not isinstance(corpo, dict) or not isinstance(corpo.get("data"), dict):
        raise ApifyErro("Chave inválida.")


def _digitos(texto: Any) -> str:
    return re.sub(r"\D", "", str(texto or ""))


def _texto(valor: Any, limite: int) -> str:
    return " ".join(str(valor or "").split())[:limite]


def lugar(item: Any) -> Lugar | None:
    """Um resultado do ator, no formato do Zé; None se não serve (sem id, sem nome, fechado)."""
    if not isinstance(item, dict) or item.get("permanentlyClosed"):
        return None
    ident, nome = _texto(item.get("placeId"), 120), _texto(item.get("title"), 120)
    if not ident or not nome:
        return None
    telefone = _digitos(item.get("phoneUnformatted") or item.get("phone"))
    if len(telefone) in (10, 11):  # o Maps às vezes vem sem o país
        telefone = f"55{telefone}"
    piores = sorted(
        (r for r in item.get("reviews") or [] if isinstance(r, dict) and r.get("text")),
        key=lambda r: float(r.get("stars") or 0),
    )
    reclamacoes = [
        _texto(r.get("text"), 300) for r in piores if float(r.get("stars") or 0) <= NOTA_RUIM
    ][:RECLAMACOES]
    link = str(item.get("url") or "")
    site = str(item.get("website") or "")
    return Lugar(
        id=ident,
        nome=nome,
        categoria=_texto(item.get("categoryName"), 80),
        endereco=_texto(item.get("address"), 200),
        telefone=telefone if 12 <= len(telefone) <= 13 else "",
        site=site[:200] if site.startswith(("http://", "https://")) else "",
        nota=float(item.get("totalScore") or 0),
        avaliacoes=int(item.get("reviewsCount") or 0),
        link=link[:300] if link.startswith("https://") else "",
        reclamacoes=reclamacoes,
    )


def buscar(
    busca: str, cidade: str, quantos: int, chave_: str, abrir: Abrir = _abrir
) -> list[Lugar]:
    """As empresas de `busca` ("clínica odontológica") em `cidade` ("Caruaru, PE")."""
    entrada = {
        "searchStringsArray": [busca[:80]],
        "locationQuery": f"{cidade[:80]}, Brasil",
        "maxCrawledPlacesPerSearch": max(1, min(quantos, 40)),
        "language": "pt-BR",
        "maxReviews": 8,
        "reviewsSort": "lowestRanking",
        "skipClosedPlaces": True,
    }
    caminho = f"/acts/{ATOR}/run-sync-get-dataset-items?timeout={ESPERA_ATOR_S}"
    itens = _chamar(_pedido(caminho, chave_, entrada), TEMPO_S, abrir)
    if not isinstance(itens, list):
        raise ApifyErro("A Apify não devolveu empresas.")
    achados = [x for x in (lugar(i) for i in itens) if x is not None]
    log.info("apify: %d empresa(s) para %r", len(achados), busca)
    return achados
