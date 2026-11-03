"""Imagens e vídeos reais na Imersão (ADR 0058): a foto de quem é, o lugar, a coisa de verdade, e o
print de uma página. Só lê a internet (a Wikimedia, ou a página pedida atrás da trava de rede) e só
grava no próprio Acervo, então passa sem perguntar; as travas estão em `zervis/imersivo/imagens.py`
e `zervis/imersivo/capturas.py`."""

import asyncio
from pathlib import Path
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.cerebro.ferramentas.modelos import _com_previas
from zervis.imersivo import capturas, imagens


def _pronto(r: dict[str, Any]) -> dict[str, Any]:
    """O que a cena precisa: o arquivo, a legenda e o crédito (que vai no rodapé, sempre)."""
    return {
        "arquivo": r["arquivo"],
        "tipo": r.get("tipo", "foto"),
        "titulo": r.get("titulo", ""),
        "legenda": r.get("legenda", ""),
        "credito": imagens.credito(r),
        "reusado": bool(r.get("reusado")),
    }


def ferramentas(acervo: Path | None) -> list[SdkMcpTool[Any]]:
    if acervo is None:
        return []

    @tool(
        "imagem_buscar",
        "Busca foto ou vídeo de verdade, livres e com crédito, para mostrar na tela: a foto de "
        'uma pessoa pública ("quem é fulano"), um lugar, uma obra, um animal, um acontecimento; '
        "vídeo para o que se move (erupção, lançamento, onda). Foto vem da Wikipédia (a foto "
        "principal da página: a melhor para pessoas e lugares) e do Wikimedia Commons; vídeo, do "
        "Commons. Busque pelo nome próprio, em português (ou em inglês, se não achar). Quando a "
        "página da Wikipédia é exatamente o pedido, a foto já volta baixada em pronta: use direto "
        "no bloco foto. Senão, devolve cada achado com a prévia logo depois: olhe e escolha o que "
        "é mesmo o pedido, em silêncio "
        "(o que você escreve entre as ferramentas é falado). Pessoa comum, sem página na "
        "Wikipédia, não: só figura pública. Baixe com imagem_baixar.",
        {
            "type": "object",
            "properties": {
                "busca": {"type": "string", "description": "Marina Silva, Machu Picchu"},
                "tipo": {"type": "string", "enum": ["foto", "video"]},
            },
            "required": ["busca"],
        },
    )
    async def imagem_buscar(args: dict[str, Any]) -> dict[str, Any]:
        tipo = "video" if args.get("tipo") == "video" else "foto"
        try:
            achados = await asyncio.to_thread(imagens.buscar, str(args.get("busca", "")), tipo)
        except imagens.ImagemErro as erro:
            return _erro(erro)
        if not achados:
            return _texto({"achados": [], "dica": "nada livre com isso; tente o nome em inglês"})
        busca = str(args.get("busca", ""))
        if tipo == "foto" and imagens.a_pagina_e_o_pedido(achados[0], busca):
            # A página é exatamente o pedido: a foto principal dela já vem baixada, sem prévias
            # (uma volta a menos do cérebro, e nada de escolher uma foto de outra pessoa).
            try:
                r = await asyncio.to_thread(imagens.baixar, achados[0].id, acervo)
                return _texto({"pronta": _pronto(r), "outros": imagens.para_resposta(achados[1:])})
            except imagens.ImagemErro:
                pass  # sem foto livre na página: segue com as prévias
        vistas = await asyncio.to_thread(imagens.previas, achados)
        return _com_previas({"achados": imagens.para_resposta(achados)}, vistas)

    @tool(
        "imagem_baixar",
        "Baixa para o Acervo a foto ou o vídeo que imagem_buscar achou (pelo id) e devolve o "
        "arquivo, a legenda e o crédito para o bloco foto (ou video) de tela_explicar. O que já "
        "foi baixado é reusado na hora. Imagem não livre é recusada.",
        {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "O id da busca: wiki:pt:Nome, commons:File:X",
                }
            },
            "required": ["id"],
        },
    )
    async def imagem_baixar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            r = await asyncio.to_thread(imagens.baixar, str(args.get("id", "")), acervo)
        except imagens.ImagemErro as erro:
            return _erro(erro)
        return _texto(_pronto(r))

    @tool(
        "pagina_capturar",
        'O print de uma página da internet para mostrar na tela ("mostra o site da loja", '
        '"mostra essa notícia"): o Chromium do Zé, sem as senhas de ninguém, abre e fotografa. '
        "Só https e só endereço público (a rede de casa nunca). Devolve o arquivo e o crédito "
        "para o bloco foto de tela_explicar. Para ler o conteúdo da página, use o navegador.",
        {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "https://..."}},
            "required": ["url"],
        },
    )
    async def pagina_capturar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            r = await asyncio.to_thread(capturas.capturar, str(args.get("url", ""))[:500], acervo)
        except capturas.CapturaErro as erro:
            return _erro(erro)
        return _texto(_pronto(r))

    return [imagem_buscar, imagem_baixar, pagina_capturar]
