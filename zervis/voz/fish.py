"""Voz pelo Fish Audio (ADR 0041), um provedor da `zervis/voz/nuvem.py`, como no LIGATIA.

Síntese em streaming (`POST /v1/tts`, PCM 16 bits a 44,1 kHz, latência baixa) com o S2.1 Pro, que
fala português (83 idiomas). A chave é conferida pelo saldo de API (`/wallet/self/api-credit`),
que é separado do crédito da plataforma: com saldo, o S2.1 Pro; sem saldo, o S2.1 Pro Free, de
graça dentro do uso justo do Fish. As vozes são as da pessoa e as mais usadas em português da
biblioteca; qualquer outra entra colando o link dela. Chave: https://fish.audio/app/developers
"""

import re
from typing import Any
from urllib.parse import quote, urlencode

from zervis.voz import nuvem

NOME = "fish"
TITULO = "Fish Audio"
DESCRICAO = "Voz natural, na nuvem. Tem modelo grátis."
ENDERECO = "https://api.fish.audio"
CADASTRO = "https://fish.audio/app/developers"
MODELO = "s2.1-pro"
MODELO_GRATIS = "s2.1-pro-free"
NOMES_MODELOS = {MODELO: "S2.1 Pro", MODELO_GRATIS: "S2.1 Pro Free"}
TAXA = 44100
IDIOMA = "pt"
POPULARES = 20  # vozes da biblioteca em português, as mais usadas
ID_DA_VOZ = re.compile(r"\b([0-9a-f]{32})\b")


def motivo(codigo: int, corpo: bytes) -> str:
    _, mensagem = nuvem.detalhe_do_erro(corpo)
    if codigo == 402:
        return "Sem saldo de API no Fish Audio (é separado do crédito da plataforma)."
    if codigo == 404:
        return "Essa voz não existe no Fish Audio."
    if codigo == 503:
        return "O Fish Audio está sobrecarregado."
    if codigo == 403:
        return "A chave não tem permissão para isso."
    return nuvem.recusa_generica(TITULO, codigo, mensagem)


def _cabecalhos(chave: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {chave}"}


def _voz(v: dict[str, Any], sua: bool) -> dict[str, str]:
    partes = ["sua"] if sua else []
    partes += [str(t) for t in (v.get("tags") or [])[:2]]
    return {"id": str(v["_id"]), "nome": str(v.get("title", "")), "detalhe": ", ".join(partes)}


def _modelos(chave: str, endereco: str, consulta: dict[str, Any]) -> list[dict[str, Any]]:
    caminho = f"/model?{urlencode(consulta)}"
    dados = nuvem.obter(endereco, caminho, _cabecalhos(chave), motivo, TITULO)
    return [
        v
        for v in dados.get("items") or []
        if isinstance(v, dict) and v.get("_id") and v.get("type", "tts") == "tts"
    ]


def vozes(chave: str, endereco: str = ENDERECO) -> list[dict[str, str]]:
    """As vozes da pessoa primeiro, depois as mais usadas em português da biblioteca."""
    proprias = _modelos(chave, endereco, {"self": "true", "page_size": 50})
    populares = _modelos(
        chave,
        endereco,
        {"language": IDIOMA, "sort_by": "task_count", "page_size": POPULARES},
    )
    vistas: set[str] = set()
    lista = []
    for v, sua in [*((v, True) for v in proprias), *((v, False) for v in populares)]:
        if str(v["_id"]) not in vistas:
            vistas.add(str(v["_id"]))
            lista.append(_voz(v, sua))
    return lista


def conta(chave: str, endereco: str = ENDERECO) -> tuple[str, str]:
    """Confere a chave pelo saldo de API; devolve (modelo, nota para a tela)."""
    dados = nuvem.obter(endereco, "/wallet/self/api-credit", _cabecalhos(chave), motivo, TITULO)
    try:
        saldo = float(dados.get("credit") or 0)
    except (TypeError, ValueError):
        saldo = 0.0
    if saldo > 0:
        valor = f"{saldo:.2f}".replace(".", ",")
        return MODELO, f"Saldo de API: US$ {valor} · {NOMES_MODELOS[MODELO]}."
    return MODELO_GRATIS, f"Sem saldo de API: {NOMES_MODELOS[MODELO_GRATIS]}, grátis no uso justo."


def voz_colada(texto: str, chave: str, endereco: str = ENDERECO) -> dict[str, str] | None:
    """O link (fish.audio/m/<id>) ou o id de uma voz da biblioteca; None se não houver id."""
    achado = ID_DA_VOZ.search(texto.lower())
    if not achado:
        return None
    caminho = f"/model/{quote(achado[1], safe='')}"
    v = nuvem.obter(endereco, caminho, _cabecalhos(chave), motivo, TITULO)
    if not isinstance(v, dict) or not v.get("_id"):
        raise nuvem.ErroVoz("Essa voz não existe no Fish Audio.")
    return _voz(v, False)


def pedido(
    texto: str, voz: str, modelo: str, chave: str
) -> tuple[str, dict[str, Any], dict[str, str]]:
    corpo = {
        "text": texto,
        "reference_id": voz,
        "format": "pcm",
        "sample_rate": TAXA,
        "latency": "low",  # como no LIGATIA (latency_mode="low"), validado em ligações reais
        "language": IDIOMA,
    }
    return "/v1/tts", corpo, {**_cabecalhos(chave), "model": modelo or MODELO}
