"""As métricas do site pela voz, só leitura (ADR 0094): como ele aparece no Google e quem o
visita. Nada aqui escreve no Google, então tudo passa sem perguntar."""

import asyncio
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.metricas_site import Metricas, MetricasErro, texto_busca, texto_visitas


def _inteiro(valor: Any, padrao: int, minimo: int, maximo: int) -> int:
    return max(minimo, min(maximo, valor)) if isinstance(valor, int) else padrao


def ferramentas(m: Metricas | None) -> list[SdkMcpTool[Any]]:
    if m is None:
        return []

    @tool(
        "site_google",
        "Como o site do usuário aparece no Google (Search Console): cliques, impressões, CTR e "
        "posição média no período, com as buscas que mais trazem gente ou as páginas mais "
        'clicadas. Use para "o blog aparece no Google?", "que buscas trazem gente ao site?", '
        '"qual página mais recebe clique do Google?". Só lê.',
        {
            "type": "object",
            "properties": {
                "dias": {"type": "integer", "description": "O período (padrão 28, até 480)"},
                "por": {"type": "string", "enum": ["buscas", "paginas"]},
                "quantos": {"type": "integer", "description": "Quantas listar (até 25)"},
            },
        },
    )
    async def site_google(args: dict[str, Any]) -> dict[str, Any]:
        dias = _inteiro(args.get("dias"), 28, 1, 480)
        por = "paginas" if args.get("por") == "paginas" else "buscas"
        quantos = _inteiro(args.get("quantos"), 10, 1, 25)
        try:
            dados = await asyncio.to_thread(m.busca, dias, por, quantos)
        except MetricasErro as erro:
            return _erro(erro)
        return _texto(texto_busca(dados))

    @tool(
        "site_visitas",
        "Quem visitou o site do usuário (Google Analytics): visitantes, visitas, visualizações e "
        "tempo médio no período; as páginas mais vistas (ou só os artigos do blog), de onde as "
        'pessoas vieram ou para onde clicaram (o WhatsApp, por exemplo). Use para "quantas '
        'pessoas visitaram o site?", "o blog está sendo lido?", "quantos clicaram no WhatsApp?". '
        "Responda falado, com os números redondos e sem ler os endereços inteiros. Só lê.",
        {
            "type": "object",
            "properties": {
                "dias": {"type": "integer", "description": "O período (padrão 28, até 365)"},
                "por": {"type": "string", "enum": ["paginas", "origens", "cliques"]},
                "blog": {"type": "boolean", "description": "Só as páginas do blog"},
                "quantos": {"type": "integer", "description": "Quantas listar (até 25)"},
            },
        },
    )
    async def site_visitas(args: dict[str, Any]) -> dict[str, Any]:
        dias = _inteiro(args.get("dias"), 28, 1, 365)
        por = str(args.get("por") or "paginas")
        quantos = _inteiro(args.get("quantos"), 10, 1, 25)
        so_blog = args.get("blog") is True
        try:
            dados = await asyncio.to_thread(m.visitas, dias, por, quantos, so_blog)
        except MetricasErro as erro:
            return _erro(erro)
        return _texto(texto_visitas(dados))

    return [site_google, site_visitas]
