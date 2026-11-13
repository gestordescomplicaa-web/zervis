"""Marketing pela voz (ADR 0091): como estão o site e o blog, pedir um artigo ou uma mudança no
site (uma sessão de código) e abrir o PR do que a sessão fez. Pedir e abrir o PR pedem o sim."""

import asyncio
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis import marketing
from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.cerebro.ferramentas.sessoes import motor_conectado
from zervis.oficina.sessoes import SessaoErro, Sessoes


def ferramentas(sessoes: Sessoes | None) -> list[SdkMcpTool[Any]]:
    if sessoes is None:
        return []
    m = marketing.PADRAO

    @tool(
        "marketing_situacao",
        "O site e o blog de quem usa: se o site está configurado, os artigos (publicados, "
        "agendados, rascunhos) por categoria, os pedidos em andamento e os PRs abertos.",
        {"type": "object", "properties": {}},
    )
    async def situacao(_args: dict[str, Any]) -> dict[str, Any]:
        def ler() -> dict[str, Any]:
            artigos = m.artigos()
            return {
                "site": m.situacao(),
                "artigos": len(artigos),
                "por_categoria": m.por_categoria(artigos),
                "ultimos": [a["titulo"] for a in artigos[:5]],
                "pedidos": m.pedidos(sessoes),
                "prs": m.prs(),
            }

        return _texto(await asyncio.to_thread(ler))

    @tool(
        "marketing_pedir",
        "Pede um artigo para o blog (tipo 'artigo', tema opcional: sem tema, a sessão escolhe "
        "pelo manual do blog do site) ou uma mudança no site (tipo 'site', diga a mudança). Abre "
        "uma sessão de código numa cópia isolada; nada vai ao ar. Quando ela terminar, use "
        "marketing_abrir_pr.",
        {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": list(marketing.NOMES)},
                "texto": {"type": "string", "description": "O tema do artigo ou a mudança"},
            },
            "required": ["tipo"],
        },
    )
    async def pedir(args: dict[str, Any]) -> dict[str, Any]:
        try:
            s = await asyncio.to_thread(
                m.pedir, sessoes, str(args["tipo"]), str(args.get("texto", "")), motor_conectado()
            )
        except (marketing.MarketingErro, SessaoErro) as erro:
            return _erro(erro)
        return _texto({"sessao": s.id, "nome": s.nome, "aviso": "O Zé avisa quando terminar."})

    @tool(
        "marketing_abrir_pr",
        "Envia ao GitHub o que uma sessão de marketing fez e abre o PR no site (artigo sempre "
        "como rascunho). Quem publica é o usuário, no merge. Sessão: o id ou o nome.",
        {
            "type": "object",
            "properties": {"sessao": {"type": "string"}},
            "required": ["sessao"],
        },
    )
    async def abrir_pr(args: dict[str, Any]) -> dict[str, Any]:
        try:
            r = await asyncio.to_thread(m.abrir_pr, sessoes, str(args["sessao"]))
        except (marketing.MarketingErro, SessaoErro) as erro:
            return _erro(erro)
        if not r.ok:
            return _erro(ValueError(r.texto))
        return _texto({"resultado": r.texto, "endereco": r.endereco})

    return [situacao, pedir, abrir_pr]
