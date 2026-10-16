"""Ferramentas das sessões de código do Zé (ADR 0015): o cérebro delega, acompanha e responde.

As sessões são agentes de código próprios do Zé (`jarvis/oficina/sessoes.py`), sem o Orca: cada
uma tem nome, pasta (o projeto), motor e a sua conversa, e continua depois de onde parou. O Zé
avisa sozinho quando uma sessão termina. Ler é livre; criar, mandar e parar pedem aprovação.
"""

import asyncio
import os
import re
from collections.abc import Callable
from pathlib import Path
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


def preparador(sessoes: Sessoes) -> Callable[[str, dict[str, Any]], str | None]:
    def preparar(nome: str, entrada: dict[str, Any]) -> str | None:
        if nome not in ("mcp__jarvis__sessao_enviar", "mcp__jarvis__sessao_continuar"):
            return None
        try:
            # Um aviso pode trocar o foco enquanto a pessoa confirma. A aprovação pertence
            # à sessão nomeada aqui, mesmo quando o modelo usou uma referência vazia.
            entrada["sessao"] = sessoes.achar(str(entrada.get("sessao", ""))).id
        except SessaoErro as erro:
            return str(erro)
        return None

    return preparar


def descritor(sessoes: Sessoes) -> Callable[[str, dict[str, Any]], str | None]:
    def descrever(nome: str, entrada: dict[str, Any]) -> str | None:
        if nome == "mcp__jarvis__sessao_criar" and str(entrada.get("tarefa", "")).strip():
            nome_sessao = " ".join(str(entrada.get("nome", "")).split())[:60]
            if not nome_sessao:
                if projeto_novo := " ".join(str(entrada.get("projeto_novo", "")).split()):
                    nome_sessao = re.sub(r"[^\w.-]+", "-", projeto_novo).strip("-.")[:60]
                else:
                    nome_sessao = Path(str(entrada.get("pasta", ""))).name or "nova"
            return f"Estou enviando sua solicitação à sessão {nome_sessao}, confirma?"
        if nome not in ("mcp__jarvis__sessao_enviar", "mcp__jarvis__sessao_continuar"):
            return None
        sessao = sessoes.achar(str(entrada.get("sessao", "")))
        return f"Estou enviando sua solicitação à sessão {sessao.nome}, confirma?"

    return descrever


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


def _pasta(sessoes: Sessoes, args: dict[str, Any]) -> str:
    """Cada sessão nova trabalha na própria pasta: sem pasta, um projeto novo com o nome dela.

    Um nome solto ("Detetive") é a pasta de mesmo nome na raiz dos projetos, criada se faltar.
    Na VPS, o cérebro pedia "uma sessão chamada teste" e travava sem saber a pasta (16/10/2026)."""
    pasta = str(args.get("pasta", "")).strip()
    novo = str(args.get("projeto_novo", "")).strip()
    raiz = sessoes.projetos_novos
    if pasta and not novo and raiz is not None and "/" not in pasta and pasta[0] not in "~.":
        if (raiz.expanduser() / pasta).is_dir():
            return str(raiz.expanduser() / pasta)
        novo = pasta
    if not pasta and not novo:
        novo = str(args.get("nome", "")).strip()
    return str(sessoes.criar_projeto(novo)) if novo else pasta


def motor_conectado() -> str:
    """O primeiro agente com conta conectada; o Claude também vale pela chave da Anthropic."""
    for motor in MOTORES:
        if motor == "claude" and os.environ.get("ANTHROPIC_API_KEY"):
            return motor
        if contas.Contas().em_uso(motor).login.is_file():
            return motor
    return MOTORES[0]


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
        "Cria uma sessão de código e, se houver, já manda a primeira tarefa. Cada sessão tem a "
        "própria pasta: sem pasta, o Zé cria um projeto novo com o nome da sessão; com o nome de "
        "um projeto existente, usa a pasta dele. A tarefa precisa ser autossuficiente: o que "
        "mudar, onde, restrições e como provar que terminou. Sem motor, usa o agente com conta "
        "conectada. O Zé avisa sozinho quando o agente terminar.",
        {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome curto da sessão"},
                "pasta": {
                    "type": "string",
                    "description": "Pasta ou nome de um projeto existente (opcional)",
                },
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
            pasta = _pasta(sessoes, args)
            if not pasta:
                raise SessaoErro("diga o nome da sessão ou a pasta do projeto")
            s = sessoes.criar(
                str(args["nome"]),
                pasta,
                motor=str(args.get("motor") or motor_conectado()),
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
