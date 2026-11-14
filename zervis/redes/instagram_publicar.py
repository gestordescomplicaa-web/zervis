"""Publicar no Instagram (ADR 0093): só com a aprovação de quem usa, um post por vez.

`instagram.py` continua só leitura (ADR 0057); escrever fica aqui, num lugar só. A API da Meta não
recebe a imagem: recebe um link público em JPEG, que os servidores dela buscam. Num carrossel, cada
slide vira um contêiner (`is_carousel_item`); o contêiner do carrossel leva a legenda; o Zé espera
ele ficar pronto e publica. Com um slide só, é uma foto.
"""

import contextlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from zervis.redes.instagram import ESPERA_S, HOSTS, VERSAO, Instagram, InstagramErro

log = logging.getLogger(__name__)

MAXIMO_SLIDES = 10  # o limite do carrossel na API
ESPERA_PRONTO_S = 90.0
INTERVALO_S = 3.0


def _recusa(erro: urllib.error.HTTPError) -> InstagramErro:
    detalhe: dict[str, Any] = {}
    with contextlib.suppress(ValueError, OSError, AttributeError):
        detalhe = json.loads(erro.read() or b"{}").get("error", {})
    codigo = detalhe.get("code")
    log.warning("instagram: publicação recusada (%s, código %s)", erro.code, codigo)
    if codigo == 190:
        return InstagramErro("Token inválido ou vencido. Cole um novo.")
    if codigo in (10, 200) or erro.code == 403:
        return InstagramErro("O token não tem permissão para publicar no Instagram.")
    if codigo in (4, 17, 32, 613, 9):
        return InstagramErro("Limite de publicações do Instagram. Tente mais tarde.")
    if codigo in (36000, 2207052, 2207026) or "image" in str(detalhe.get("message", "")).lower():
        return InstagramErro("O Instagram não conseguiu buscar as imagens do post.")
    return InstagramErro("O Instagram recusou a publicação.")


def _chamar(
    ig: Instagram, base: str, caminho: str, params: dict[str, str], token: str, post: bool
) -> dict[str, Any]:
    dados = urllib.parse.urlencode({**params, "access_token": token})
    url = f"{HOSTS[base]}/{VERSAO}/{caminho.lstrip('/')}"
    pedido = (
        urllib.request.Request(url, data=dados.encode(), method="POST")  # noqa: S310 (um dos HOSTS)
        if post
        else urllib.request.Request(f"{url}?{dados}")  # noqa: S310
    )
    try:
        with ig.abrir(pedido, timeout=ESPERA_S) as resposta:
            corpo = json.loads(resposta.read() or b"{}")
    except urllib.error.HTTPError as erro:
        raise _recusa(erro) from erro
    except (urllib.error.URLError, OSError, ValueError) as erro:
        raise InstagramErro("Sem conexão com o Instagram.") from erro
    return corpo if isinstance(corpo, dict) else {}


def publicar(
    ig: Instagram,
    imagens: list[str],
    legenda: str,
    dormir: Callable[[float], None] = time.sleep,
    prazo_s: float = ESPERA_PRONTO_S,
) -> str:
    """Publica as imagens (links públicos em JPEG) com a legenda e devolve o link do post."""
    if not imagens or len(imagens) > MAXIMO_SLIDES:
        raise InstagramErro(f"Um post tem de 1 a {MAXIMO_SLIDES} imagens.")
    base, conta, token = ig._token()
    if len(imagens) == 1:
        principal = _chamar(
            ig, base, f"{conta}/media", {"image_url": imagens[0], "caption": legenda}, token, True
        )
    else:
        filhos = [
            str(
                _chamar(
                    ig, base, f"{conta}/media",
                    {"image_url": url, "is_carousel_item": "true"}, token, True,
                ).get("id", "")
            )
            for url in imagens
        ]  # fmt: skip
        if not all(filhos):
            raise InstagramErro("O Instagram não aceitou uma das imagens.")
        principal = _chamar(
            ig, base, f"{conta}/media",
            {"media_type": "CAROUSEL", "children": ",".join(filhos), "caption": legenda},
            token, True,
        )  # fmt: skip
    criado = str(principal.get("id", ""))
    if not criado:
        raise InstagramErro("O Instagram recusou a publicação.")
    fim = time.monotonic() + prazo_s
    while True:
        estado = _chamar(ig, base, criado, {"fields": "status_code"}, token, False)
        situacao = str(estado.get("status_code", ""))
        if situacao == "FINISHED":
            break
        if situacao in ("ERROR", "EXPIRED"):
            raise InstagramErro("O Instagram não conseguiu preparar o post.")
        if time.monotonic() > fim:
            raise InstagramErro("O Instagram demorou demais para preparar o post.")
        dormir(INTERVALO_S)
    publicado = str(
        _chamar(ig, base, f"{conta}/media_publish", {"creation_id": criado}, token, True).get(
            "id", ""
        )
    )
    if not publicado:
        raise InstagramErro("O Instagram não confirmou a publicação.")
    link = _chamar(ig, base, publicado, {"fields": "permalink"}, token, False)
    return str(link.get("permalink", ""))
