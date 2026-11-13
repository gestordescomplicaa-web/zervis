"""Marketing pela voz (ADR 0091 e 0092): como estão o site e o blog, pedir um artigo ou uma
mudança no site (uma sessão de código), abrir o PR, publicar com o "aprovado" de quem usa e agendar
artigos. Tudo, menos a situação, pede o sim."""

import asyncio
import json
from datetime import datetime
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis import marketing
from zervis.automacoes.agenda import FUSO
from zervis.automacoes.jobs import JobErro, Jobs
from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.cerebro.ferramentas.sessoes import motor_conectado
from zervis.oficina.sessoes import SessaoErro, Sessoes


def ferramentas(sessoes: Sessoes | None, jobs: Jobs | None = None) -> list[SdkMcpTool[Any]]:
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

    @tool(
        "marketing_publicar",
        "Publica o que uma sessão de marketing fez, quando o usuário aprova ('aprovado', 'pode "
        "publicar'). Num artigo, a sessão tira o rascunho e encaixa as respostas do usuário às "
        "perguntas de experiência, se ele der (respostas, opcional; sem elas, os trechos saem); "
        "depois o Zé envia ao site e avisa quando o deploy terminar. Sessão: o id ou o nome.",
        {
            "type": "object",
            "properties": {
                "sessao": {"type": "string"},
                "respostas": {"type": "string", "description": "O que o usuário respondeu"},
            },
            "required": ["sessao"],
        },
    )
    async def publicar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            r = await asyncio.to_thread(
                m.publicar, sessoes, str(args["sessao"]), str(args.get("respostas", ""))
            )
        except (marketing.MarketingErro, SessaoErro) as erro:
            return _erro(erro)
        if not r.ok:
            return _erro(ValueError(r.texto))
        return _texto({"resultado": r.texto})

    ferramentas_ = [situacao, pedir, abrir_pr, publicar]
    if jobs is None:
        return ferramentas_

    @tool(
        "marketing_agendar",
        "Agenda artigos do blog sozinhos: em cada vez, uma sessão escreve um artigo (sem tema, "
        "ela escolhe pelo manual do site), o PR abre sozinho e publicar espera o 'aprovado' do "
        "usuário. quando: 'cron 0 9 * * 1,4' (segunda e quinta às 9h), 'a cada 3d'... Para "
        "listar ou remover, use as ferramentas de automações.",
        {
            "type": "object",
            "properties": {
                "quando": {"type": "string"},
                "tema": {"type": "string", "description": "Opcional: o mesmo tema sempre"},
            },
            "required": ["quando"],
        },
    )
    async def agendar(args: dict[str, Any]) -> dict[str, Any]:
        texto = json.dumps({"tema": str(args.get("tema", ""))}, ensure_ascii=False)
        try:
            job = jobs.criar(
                "Artigo do blog", str(args["quando"]), "artigo", texto, datetime.now(FUSO)
            )
        except JobErro as erro:
            return _erro(erro)
        return _texto({"criada": job.resumo(), "id": job.id, "proxima": job.proxima})

    return [*ferramentas_, agendar]
