"""Ferramentas da oficina: projetos e agentes do Orca (delegar, acompanhar, responder)."""

import asyncio
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from jarvis.cerebro.ferramentas.comum import _erro, _texto
from jarvis.oficina.monitor import Monitor
from jarvis.oficina.oficina import AGENTES, STATUS, Oficina
from jarvis.oficina.orca import OrcaErro


def ferramentas(oficina: Oficina, monitor: Monitor) -> list[SdkMcpTool[Any]]:
    @tool(
        "oficina_projetos",
        "Lista os projetos abertos no Orca (nome, pasta e agentes que estão rodando neles).",
        {},
    )
    async def projetos(_: dict[str, Any]) -> dict[str, Any]:
        try:
            lista = await asyncio.to_thread(oficina.projetos)
        except OrcaErro as erro:
            return _erro(erro)
        return _texto([{"nome": p.nome, "pasta": p.caminho, "agentes": p.agentes} for p in lista])

    @tool(
        "oficina_delegar",
        "Delega uma tarefa de código a um agente novo do Orca num projeto existente. A tarefa "
        "precisa ser autossuficiente: o que mudar, onde, restrições e como provar que terminou. "
        "O JARVIS avisa sozinho quando o agente terminar, falhar ou perguntar algo.",
        {
            "type": "object",
            "properties": {
                "tarefa": {"type": "string", "description": "Especificação completa da tarefa"},
                "projeto": {"type": "string", "description": "Nome do projeto no Orca"},
                "agente": {"type": "string", "enum": sorted(AGENTES)},
            },
            "required": ["tarefa", "projeto", "agente"],
        },
    )
    async def delegar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            recibo = await asyncio.to_thread(
                oficina.delegar, args["tarefa"], args["projeto"], args["agente"]
            )
        except OrcaErro as erro:
            return _erro(erro)
        return _texto({"delegado": True, **recibo})

    @tool(
        "oficina_situacao",
        "Situação das tarefas que o JARVIS delegou e as perguntas dos agentes ainda sem resposta.",
        {},
    )
    async def situacao(_: dict[str, Any]) -> dict[str, Any]:
        try:
            tarefas = await asyncio.to_thread(oficina.situacao)
        except OrcaErro as erro:
            return _erro(erro)
        perguntas = [vars(p) for p in monitor.perguntas.values()]
        return _texto({"tarefas": tarefas, "perguntas_sem_resposta": perguntas})

    @tool(
        "oficina_responder",
        "Responde a uma pergunta que um agente fez (use o id de oficina_situacao).",
        {"pergunta_id": str, "resposta": str},
    )
    async def responder(args: dict[str, Any]) -> dict[str, Any]:
        try:
            await asyncio.to_thread(oficina.responder, args["pergunta_id"], args["resposta"])
        except OrcaErro as erro:
            return _erro(erro)
        monitor.perguntas.pop(args["pergunta_id"], None)
        return _texto("Resposta enviada.")

    @tool(
        "oficina_saida",
        "Últimas linhas da tela de um agente delegado (use o dispatch de oficina_situacao).",
        {"dispatch": str},
    )
    async def saida(args: dict[str, Any]) -> dict[str, Any]:
        try:
            linhas = await asyncio.to_thread(oficina.ler_saida, args["dispatch"])
        except OrcaErro as erro:
            return _erro(erro)
        return _texto("\n".join(linhas))

    @tool(
        "oficina_criar_projeto",
        "Cria um projeto novo: pasta na raiz de projetos, git iniciado e registro no Orca. "
        "Confirme o nome exato com o usuário antes. Depois, para trabalhar nele, delegue.",
        {"nome": str},
    )
    async def criar_projeto(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _texto(await asyncio.to_thread(oficina.criar_projeto, args["nome"]))
        except OrcaErro as erro:
            return _erro(erro)

    @tool(
        "oficina_nova_frente",
        "Abre uma frente nova (worktree com branch própria) num projeto existente, para um "
        "agente trabalhar sem mexer no que está em andamento.",
        {"projeto": str, "nome": str},
    )
    async def nova_frente(args: dict[str, Any]) -> dict[str, Any]:
        try:
            recibo = await asyncio.to_thread(oficina.nova_frente, args["projeto"], args["nome"])
        except OrcaErro as erro:
            return _erro(erro)
        return _texto(recibo)

    @tool(
        "oficina_marcar",
        "Muda o status de um projeto no quadro do Orca. Arquivar é marcar como concluído.",
        {
            "type": "object",
            "properties": {
                "projeto": {"type": "string"},
                "status": {"type": "string", "enum": list(STATUS)},
            },
            "required": ["projeto", "status"],
        },
    )
    async def marcar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            recibo = await asyncio.to_thread(oficina.marcar, args["projeto"], args["status"])
        except OrcaErro as erro:
            return _erro(erro)
        return _texto(recibo)

    @tool(
        "oficina_renomear",
        "Muda o nome com que um projeto aparece no Orca (a pasta continua a mesma).",
        {"projeto": str, "novo_nome": str},
    )
    async def renomear(args: dict[str, Any]) -> dict[str, Any]:
        try:
            recibo = await asyncio.to_thread(oficina.renomear, args["projeto"], args["novo_nome"])
        except OrcaErro as erro:
            return _erro(erro)
        return _texto(recibo)

    @tool(
        "oficina_mandar_texto",
        "Escreve uma mensagem numa sessão de agente que JÁ ESTÁ ABERTA no projeto (a que o "
        "o usuário está usando), sem criar agente novo. Use quando ele pedir para mandar, dizer ou "
        "escrever algo para o Claude ou o Codex de um projeto. `sessao` filtra pelo título ou "
        "agente quando houver mais de uma.",
        {
            "type": "object",
            "properties": {
                "projeto": {"type": "string"},
                "texto": {"type": "string"},
                "sessao": {"type": "string"},
            },
            "required": ["projeto", "texto"],
        },
    )
    async def mandar_texto(args: dict[str, Any]) -> dict[str, Any]:
        try:
            recibo = await asyncio.to_thread(
                oficina.mandar_texto, args["projeto"], args["texto"], args.get("sessao", "")
            )
        except OrcaErro as erro:
            return _erro(erro)
        return _texto({"enviado": True, **recibo})

    return [
        projetos,
        delegar,
        situacao,
        responder,
        saida,
        mandar_texto,
        criar_projeto,
        nova_frente,
        marcar,
        renomear,
    ]
