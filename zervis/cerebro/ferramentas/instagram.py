"""O Instagram do Zé pela voz, só leitura (ADR 0057): o perfil e as publicações com as métricas.
Nada aqui publica, responde ou comenta, então tudo passa sem perguntar."""

import asyncio
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis import fuso
from zervis.redes import analise
from zervis.redes.instagram import Instagram, InstagramErro


def _texto(texto: str, erro: bool = False) -> dict[str, Any]:
    resposta: dict[str, Any] = {"content": [{"type": "text", "text": texto}]}
    if erro:
        resposta["is_error"] = True
    return resposta


def _inteiro(valor: Any, padrao: int, minimo: int, maximo: int) -> int:
    return max(minimo, min(maximo, valor)) if isinstance(valor, int) else padrao


def ferramentas(ig: Instagram | None) -> list[SdkMcpTool[Any]]:
    if ig is None:
        return []

    @tool(
        "instagram_perfil",
        "O perfil do Instagram do usuário agora (seguidores, seguindo, publicações) e como ele "
        "foi no período (alcance, visualizações, contas engajadas, interações, seguidores "
        'ganhos), com quantas vezes publicou e a média por publicação. Use para "como está meu '
        'Instagram?", "quantos seguidores eu tenho?", "como foi o mês?". Só lê.',
        {
            "type": "object",
            "properties": {"dias": {"type": "integer", "description": "O período, até 30 dias"}},
        },
    )
    async def instagram_perfil(args: dict[str, Any]) -> dict[str, Any]:
        dias = _inteiro(args.get("dias"), 30, 1, 30)

        def ler() -> str:
            perfil = ig.perfil()
            try:
                periodo = ig.conta_no_periodo(dias)
            except InstagramErro:
                periodo = {}  # conta pequena ou sem a permissão: o resto ainda serve
            return analise.resumo(perfil, periodo, ig.posts(), dias, ig.agora())

        try:
            return _texto(await asyncio.to_thread(ler))
        except InstagramErro as erro:
            return _texto(str(erro), erro=True)

    @tool(
        "instagram_posts",
        "As publicações do Instagram do usuário com as métricas de cada uma, já ordenadas: "
        '"qual post me rendeu mais visualizações?", "meus reels com mais alcance no mês", '
        '"o que mais salvaram?", "minhas últimas publicações". Filtre pelo tipo e pelos últimos '
        "dias quando o pedido disser. Responda falado: qual, quando, os números e o porquê "
        "provável (tema, formato), sem ler os links.",
        {
            "type": "object",
            "properties": {
                "ordem": {"type": "string", "enum": list(analise.ORDENS)},
                "tipo": {"type": "string", "enum": ["todos", *analise.TIPOS]},
                "dias": {"type": "integer", "description": "Só os últimos N dias (0 = todas)"},
                "quantos": {"type": "integer", "description": "Quantas listar (até 20)"},
            },
        },
    )
    async def instagram_posts(args: dict[str, Any]) -> dict[str, Any]:
        ordem = str(args.get("ordem") or "visualizacoes")
        tipo = str(args.get("tipo") or "todos")
        dias = _inteiro(args.get("dias"), 0, 0, 3650)
        quantos = _inteiro(args.get("quantos"), 5, 1, 20)
        try:
            posts = await asyncio.to_thread(ig.posts)
        except InstagramErro as erro:
            return _texto(str(erro), erro=True)
        return _texto(analise.ranking(posts, ordem, dias, tipo, quantos, ig.agora(), fuso.local()))

    return [instagram_perfil, instagram_posts]
