"""As fotos do Pixabay nos vídeos (ADR 0124): fotos modernas de negócio, sem crédito.

A licença do Pixabay permite o uso comercial sem dar crédito (o que o vídeo e a legenda pedem,
ADR 0121). Com a chave de quem usa (`<config>/pixabay.key`, 0600, posta no cartão Vídeos), a
busca livre vai primeiro ao Pixabay e só depois ao Commons. As regras da escolha são as mesmas
(as palavras do pedido nas etiquetas, nada de gente), e a foto é baixada para a pasta do vídeo
(o Pixabay não deixa usar o endereço dele direto). Sem a chave, nada muda.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from zervis import lugares
from zervis.imersivo.imagens import Achado, ImagemErro

log = logging.getLogger(__name__)

ARQUIVO = lugares.CONFIG / "pixabay.key"
API = "https://pixabay.com/api/"
HOSTS = frozenset({"pixabay.com", "cdn.pixabay.com"})
RESULTADOS = 20
FOTO_MAX = 15 * 1024 * 1024
TEMPO_S = 20
_CHAVE = re.compile(r"\d{5,12}-[0-9a-f]{20,40}")


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
        raise ImagemErro("Chave inválida.")
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".tmp")
    temporario.write_text(texto)
    os.chmod(temporario, 0o600)
    temporario.replace(arquivo)


def _ler(url: str, limite: int) -> bytes:
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or (p.hostname or "") not in HOSTS:
        raise ImagemErro("endereço fora do Pixabay")
    pedido = urllib.request.Request(url, headers={"User-Agent": "Zervis"})  # noqa: S310 (conferido)
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_S) as r:  # noqa: S310 (conferido)
            dados: bytes = r.read(limite + 1)
    except urllib.error.HTTPError as erro:
        raise ImagemErro("Chave inválida." if erro.code in (400, 401, 403) else "falhou") from None
    except (urllib.error.URLError, OSError):
        raise ImagemErro("Sem conexão com o Pixabay.") from None
    if len(dados) > limite:
        raise ImagemErro("arquivo grande demais")
    return dados


def buscar(busca: str, chave_: str, ler: Any = _ler) -> list[Achado]:
    """As fotos (só fotos, busca segura) para o pedido em inglês; as etiquetas dizem o que é."""
    consulta = urllib.parse.urlencode(
        {"key": chave_, "q": busca[:100], "image_type": "photo", "safesearch": "true",
         "per_page": str(RESULTADOS)}
    )  # fmt: skip
    try:
        dados = json.loads(ler(f"{API}?{consulta}", 2 * 1024 * 1024))
    except ValueError:
        raise ImagemErro("o Pixabay respondeu algo que não é JSON") from None
    achados = []
    for h in dados.get("hits") or [] if isinstance(dados, dict) else []:
        url = str(h.get("largeImageURL") or "")
        if not url or not h.get("id"):
            continue
        etiquetas = str(h.get("tags") or "")[:300]
        achados.append(
            Achado(
                id=f"pixabay:{int(h['id'])}", titulo=etiquetas, descricao=etiquetas,
                tipo="foto", licenca="Pixabay", autor=str(h.get("user") or "")[:60],
                previa=url, pagina=str(h.get("pageURL") or "")[:240], atribuicao=False,
                categorias=etiquetas,
            )
        )  # fmt: skip
    return achados


def baixar(achado: Achado, pasta: Path, ler: Any = _ler) -> Path:
    """A foto na pasta do vídeo (`imagens/pixabay/<id>.jpg`); reusa se já estiver lá."""
    numero = achado.id.removeprefix("pixabay:")
    if not numero.isdigit():
        raise ImagemErro("foto desconhecida")
    destino = pasta / "imagens" / "pixabay" / f"{numero}.jpg"
    if not destino.is_file():
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(ler(achado.previa, FOTO_MAX))
    return destino
