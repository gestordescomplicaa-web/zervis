"""A capa do Reels (ADR 0123): uma peça à parte do vídeo, sobre o tema, não um quadro dele.

O diretor escreve o tema como título de capa (de 2 a 5 palavras: "Cobrança no automático"), a
palavra em destaque, o objeto do tema (o ícone) e qual foto da marca é o retrato de quem fala. O
Zé desenha a peça com a mesma página dos quadros (a cena "capa", parada): o fundo escuro na cor
da marca, o título enorme à esquerda, o ícone do tema num selo e o retrato fundido à direita (as
bordas somem no fundo; sem recorte). Sem retrato, o título e o ícone vão ao centro. O perfil do
Instagram recorta a capa em 3:4; o título fica dentro do recorte. Ela vai ao Instagram como
`cover_url` e é o pôster da prévia no painel.
"""

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PIL import Image

from zervis.video import biblioteca, captura

DURACAO = 1.0
MOMENTO = 0.5  # a peça é parada: qualquer instante serve
PALAVRAS = 5
LIMITE = 40


def texto_da_capa(capa: str, titulo: str, gancho: str) -> str:
    """O título da capa: o do diretor; sem ele, o título ou o gancho, se forem curtos."""
    for candidato in (capa, titulo, gancho):
        limpo = " ".join(str(candidato or "").split())
        if limpo and len(limpo) <= LIMITE and len(limpo.split()) <= PALAVRAS + 1:
            return limpo
    return " ".join(" ".join(str(capa or titulo or gancho).split()).split()[:PALAVRAS])


def dados(
    video: dict[str, Any],
    texto: str,
    destaque: str = "",
    icone: str = "",
    retrato: str = "",
) -> dict[str, Any]:
    """Os dados da página para a capa, a partir dos do vídeo (a marca, o estilo, as fontes).
    `icone` é o objeto do tema (achado na biblioteca); `retrato`, o endereço da foto."""
    nome_icone = biblioteca.achar(icone) if icone else ""
    marca = video.get("marca") or {}
    cena = {
        "tipo": "capa", "fala": "", "texto": texto, "camera": "parado", "transicao": "corte",
        "fundo": "escuro", "composicao": "capa", "inicio": 0.0, "fim": DURACAO, "palavras": [],
        "destaque": destaque if destaque and destaque.lower() in texto.lower() else "",
        "icone": nome_icone, "imagem": retrato, "legenda": "cinetica",
        "assinatura": f"@{marca['instagram']}" if marca.get("instagram") else "",
    }  # fmt: skip
    icones = dict(video.get("icones") or {})
    if nome_icone:
        icones[nome_icone] = biblioteca.todos()[nome_icone]
    return {
        **video,
        "duracao": DURACAO,
        "cenas": [cena],
        "falas": [{"texto": "", "inicio": 0.0, "dur": 0.0, "palavras": []}],
        "volume": [0.0] * round(DURACAO * captura.FPS),
        "icones": icones,
        "estilo": {**video.get("estilo", {}), "onda": False},
    }


def desenhar(
    video: dict[str, Any],
    texto: str,
    pasta: Path,
    destaque: str = "",
    icone: str = "",
    retrato: Path | None = None,
    capturar: Callable[..., list[Path]] = captura.capturar,
) -> Path:
    """`capa.jpg` na pasta do vídeo, desenhada pela página dos quadros."""
    arquivo = pasta / "capa.js"
    uri = retrato.resolve().as_uri() if retrato else ""
    conteudo = json.dumps(dados(video, texto, destaque, icone, uri), ensure_ascii=False)
    arquivo.write_text(f"window.VIDEO = {conteudo};\n")
    try:
        [quadro] = capturar(
            captura.url_da_pagina(arquivo), pasta / "capa-quadro",
            int(video["largura"]), int(video["altura"]), tempos=[MOMENTO],
        )  # fmt: skip
        saida = pasta / "capa.jpg"
        with Image.open(quadro) as imagem:
            imagem.convert("RGB").save(saida, "JPEG", quality=92)
    finally:
        arquivo.unlink(missing_ok=True)
        shutil.rmtree(pasta / "capa-quadro", ignore_errors=True)
    return saida
