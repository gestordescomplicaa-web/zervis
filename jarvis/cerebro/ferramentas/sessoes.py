"""Ferramentas das sessões de código do Zé (ADR 0015): o cérebro delega, acompanha e responde.

As sessões são agentes de código próprios do Zé (`jarvis/oficina/sessoes.py`), sem o Orca: cada
uma tem nome, pasta (o projeto), motor e a sua conversa, e continua depois de onde parou. O Zé
avisa sozinho quando uma sessão termina. Ler é livre; criar, mandar e parar pedem aprovação.
"""

import asyncio
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from jarvis.cerebro import contas
from jarvis.cerebro.ferramentas.comum import _erro, _texto
from jarvis.oficina.sessoes import MOTORES, Sessao, SessaoErro, Sessoes

ULTIMAS = 12  # mensagens que sessao_ler devolve
_REF = {"type": "string", "description": "Id ou nome da sessão; vazio: a sessão em foco"}
SESSAO: dict[str, Any] = {"type": "object", "properties": {"sessao": _REF}}
SESSAO_E_TEXTO: dict[str, Any] = {
    "type": "object",
    "properties": {"sessao": _REF, "texto": {"type": "string"}},
    "required": ["texto"],
}


def _resumo(s: Sessao) -> dict[str, Any]:
    return {
        "id": s.id,
        "nome": s.nome,
        "pasta": s.pasta,
        "motor": s.motor,
        "estado": s.estado,
        "ultimo_recado": s.resumo,
        "copia_isolada": bool(s.branch),
    }


def ferramentas(sessoes: Sessoes | None) -> list[SdkMcpTool[Any]]:
    if sessoes is None:
        return []

    @tool(
        "sessoes_listar",
        "Lista as sessões de código do Zé: nome, pasta, motor, estado (parada, trabalhando, erro) "
        "e o último recado do agente.",
        {},
    )
    async def listar(_: dict[str, Any]) -> dict[str, Any]:
        lista = await asyncio.to_thread(sessoes.listar)
        return _texto([_resumo(s) for s in lista])

    @tool(
        "sessao_criar",
        "Cria uma sessão de código numa pasta de projeto e, se houver, já manda a primeira tarefa. "
        "A tarefa precisa ser autossuficiente: o que mudar, onde, restrições e como provar que "
        "terminou. Para um projeto que ainda não existe, use projeto_novo com o nome da pasta. "
        "O Zé avisa sozinho quando o agente terminar.",
        {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome curto da sessão"},
                "pasta": {"type": "string", "description": "Pasta existente do projeto"},
                "projeto_novo": {"type": "string", "description": "Nome de um projeto novo"},
                "tarefa": {"type": "string", "description": "A primeira tarefa (opcional)"},
                "motor": {"type": "string", "enum": list(MOTORES)},
                "isolada": {
                    "type": "boolean",
                    "description": "Cópia isolada: mexe no projeto só com aprovação",
                },
            },
            "required": ["nome"],
        },
    )
    async def criar(args: dict[str, Any]) -> dict[str, Any]:
        def fazer() -> Sessao:
            pasta = str(args.get("pasta", "")).strip()
            if novo := str(args.get("projeto_novo", "")).strip():
                pasta = str(sessoes.criar_projeto(novo))
            if not pasta:
                raise SessaoErro("diga a pasta do projeto ou o nome de um projeto novo")
            s = sessoes.criar(
                str(args["nome"]),
                pasta,
                motor=str(args.get("motor") or MOTORES[0]),
                isolada=bool(args.get("isolada")),
                origem="voz",
            )
            if tarefa := str(args.get("tarefa", "")).strip():
                s = sessoes.enviar(s.id, tarefa)
            return s

        try:
            s = await asyncio.to_thread(fazer)
        except SessaoErro as erro:
            return _erro(erro)
        return _texto({"criada": True, **_resumo(s)})

    @tool(
        "sessao_enviar",
        "Manda uma mensagem a uma sessão: uma tarefa nova ou a resposta a uma pergunta do agente. "
        "Se ela estiver trabalhando, a mensagem entra na fila do agente. Sessão: o id ou o nome; "
        "vazio é a sessão em foco (a do último aviso ou a aberta na tela).",
        SESSAO_E_TEXTO,
    )
    async def enviar(args: dict[str, Any]) -> dict[str, Any]:
        def fazer() -> Sessao:
            return sessoes.enviar(sessoes.achar(str(args.get("sessao", ""))).id, args["texto"])

        try:
            s = await asyncio.to_thread(fazer)
        except SessaoErro as erro:
            return _erro(erro)
        return _texto({"enviada": True, **_resumo(s)})

    @tool(
        "sessao_ler",
        f"O andamento de uma sessão: estado e as últimas {ULTIMAS} mensagens (pedidos, comandos "
        "e arquivos que o agente mexeu, respostas). Sessão: o id ou o nome; vazio é a em foco.",
        SESSAO,
    )
    async def ler(args: dict[str, Any]) -> dict[str, Any]:
        def achar() -> Sessao:
            s = sessoes.achar(str(args.get("sessao", "")))
            sessoes.focar(s.id)
            return s

        try:
            s = await asyncio.to_thread(achar)
        except SessaoErro as erro:
            return _erro(erro)
        mensagens = await asyncio.to_thread(sessoes.mensagens, s.id)
        recentes = [{"quem": m["quem"], "texto": m["texto"][:1500]} for m in mensagens[-ULTIMAS:]]
        return _texto({**_resumo(s), "mensagens": recentes})

    @tool(
        "sessao_trocar",
        "Troca o agente (claude ou codex) ou a conta de uma sessão parada, sem perder a conversa: "
        "na mesma agente a conversa continua inteira; noutro, ele recebe a passagem do que já foi "
        "feito. Use quando o usuário pedir ou quando a conta bater o limite. Conta: o nome dela "
        "(vazio: a que está em uso para aquele agente).",
        {
            "type": "object",
            "properties": {
                "sessao": _REF,
                "agente": {"type": "string", "enum": list(MOTORES)},
                "conta": {"type": "string", "description": "Nome da conta (opcional)"},
            },
            "required": ["agente"],
        },
    )
    async def trocar(args: dict[str, Any]) -> dict[str, Any]:
        def fazer() -> tuple[Sessao, str]:
            agente, nome = str(args["agente"]), str(args.get("conta", "")).strip().casefold()
            conta = ""
            if nome:
                achada = next(
                    (c for c in contas.Contas().listar(agente) if c.nome.casefold() == nome), None
                )
                if achada is None:
                    raise SessaoErro(f"não há conta {args['conta']} do {agente}")
                conta = achada.id
            return sessoes.trocar(sessoes.achar(str(args.get("sessao", ""))).id, agente, conta)

        try:
            s, aviso = await asyncio.to_thread(fazer)
        except SessaoErro as erro:
            return _erro(erro)
        return _texto({"trocada": True, "aviso": aviso, **_resumo(s)})

    @tool(
        "sessao_parar",
        "Para uma sessão que está trabalhando (a conversa fica). Sessão: id ou nome; vazio é a "
        "em foco.",
        SESSAO,
    )
    async def parar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            s = await asyncio.to_thread(
                lambda: sessoes.parar(sessoes.achar(str(args.get("sessao", ""))).id)
            )
        except SessaoErro as erro:
            return _erro(erro)
        return _texto({"parada": True, **_resumo(s)})

    @tool(
        "sessao_continuar",
        "Retoma a tarefa que um reinício do Zé (ou o terminal fechando) interrompeu numa sessão: o "
        "agente recebe o pedido de novo e continua de onde parou. Use quando a pessoa disser "
        '"continua" depois do aviso de tarefa interrompida. Sessão: id ou nome; vazio é a em foco.',
        SESSAO,
    )
    async def continuar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            s = await asyncio.to_thread(
                lambda: sessoes.continuar_interrompida(
                    sessoes.achar(str(args.get("sessao", ""))).id
                )
            )
        except SessaoErro as erro:
            return _erro(erro)
        return _texto({"continuando": True, **_resumo(s)})

    return [listar, criar, enviar, ler, trocar, parar, continuar]
