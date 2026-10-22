"""Ferramentas das automações: lembretes e perguntas agendadas."""

from datetime import datetime
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis.automacoes.agenda import FUSO
from zervis.automacoes.jobs import JobErro, Jobs
from zervis.cerebro.ferramentas.comum import _erro, _texto


def ferramentas(jobs: Jobs | None) -> list[SdkMcpTool[Any]]:
    quando_doc = (
        "quando: 'em 2m', 'em 1h30m' (uma vez, daqui a); 'a cada 2h' (intervalo); "
        "'cron 0 9 * * 1-5' (minuto hora dia mês dia-da-semana, 0 = domingo); "
        "'2026-10-07 08:00' (data e hora locais, uma vez). Calcule a partir da data e hora "
        "do começo da mensagem."
    )
    esquema_job = {
        "type": "object",
        "properties": {
            "quando": {"type": "string"},
            "texto": {"type": "string"},
            "nome": {"type": "string", "description": "Nome curto para listar"},
        },
        "required": ["quando", "texto"],
    }

    def _criar(tipo: str, args: dict[str, Any]) -> dict[str, Any]:
        if jobs is None:
            return _erro(ValueError("automações indisponíveis"))
        try:
            job = jobs.criar(
                str(args.get("nome", "")), args["quando"], tipo, args["texto"], datetime.now(FUSO)
            )
        except JobErro as erro:
            return _erro(erro)
        return _texto({"criada": job.resumo(), "id": job.id, "proxima": job.proxima})

    @tool(
        "automacao_lembrete",
        "Agenda um lembrete: na hora, o texto é falado ao usuário (sem gastar modelo). O lembrete "
        "só fala o texto, não confere nada: para saber quando um n8n cai ou volta, não crie "
        "lembrete, o vigia do n8n já avisa as duas coisas sozinho. " + quando_doc,
        esquema_job,
    )
    async def automacao_lembrete(args: dict[str, Any]) -> dict[str, Any]:
        return _criar("lembrete", args)

    @tool(
        "automacao_pergunta",
        "Agenda uma pergunta ao cérebro (ex.: 'diga a previsão do tempo de hoje'): na hora, ela "
        "é respondida só com pesquisa e leitura da internet e a resposta é falada. " + quando_doc,
        esquema_job,
    )
    async def automacao_pergunta(args: dict[str, Any]) -> dict[str, Any]:
        return _criar("pergunta", args)

    @tool("automacoes_listar", "Lista as automações (lembretes e perguntas agendadas).", {})
    async def automacoes_listar(_: dict[str, Any]) -> dict[str, Any]:
        lista = (
            [{"id": j.id, "resumo": j.resumo(), "status": j.ultimo_status} for j in jobs.listar()]
            if jobs
            else []
        )
        return _texto(lista or "Nenhuma automação.")

    @tool(
        "automacao_mudar",
        "Pausa, retoma ou remove uma automação (id de automacoes_listar).",
        {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "acao": {"type": "string", "enum": ["pausar", "retomar", "remover"]},
            },
            "required": ["id", "acao"],
        },
    )
    async def automacao_mudar(args: dict[str, Any]) -> dict[str, Any]:
        if jobs is None:
            return _erro(ValueError("automações indisponíveis"))
        try:
            if args["acao"] == "pausar":
                job = jobs.pausar(args["id"])
            elif args["acao"] == "retomar":
                job = jobs.retomar(args["id"], datetime.now(FUSO))
            else:
                job = jobs.remover(args["id"])
        except JobErro as erro:
            return _erro(erro)
        return _texto({args["acao"]: job.resumo()})

    return [automacao_lembrete, automacao_pergunta, automacoes_listar, automacao_mudar]
