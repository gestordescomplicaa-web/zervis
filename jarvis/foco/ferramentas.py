"""As ferramentas do Foco para o cérebro (servidor MCP "foco", montado pelo laço).

Todas livres: são a organização do próprio usuário, reversíveis, e ele acabou de pedir. As
respostas já vêm prontas para falar curto.
"""

import json
from typing import Any

from claude_agent_sdk import McpSdkServerConfig, SdkMcpTool, create_sdk_mcp_server, tool

from jarvis.foco.frentes import LIMITE, Foco, FocoErro, Frente

SERVIDOR = "foco"
NOMES = (
    "foco_ver",
    "foco_criar",
    "foco_atualizar",
    "foco_focar",
    "foco_concluir",
    "foco_ideia",
    "foco_juntar",
)
LIVRES = [f"mcp__{SERVIDOR}__{n}" for n in NOMES]


def _texto(dados: Any) -> dict[str, Any]:
    texto = dados if isinstance(dados, str) else json.dumps(dados, ensure_ascii=False)
    return {"content": [{"type": "text", "text": texto}]}


def _erro(erro: Exception) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"Não deu: {erro}"}], "is_error": True}


def _dict(f: Frente) -> dict[str, Any]:
    d = {
        "frente": f.titulo,
        "estado": f.estado,
        "proximo_passo": f.proximo_passo,
        "bloqueio": f.bloqueio,
        "projeto": f.projeto,
        "atual": f.atual,
        "desde": f.criada[:10],
        "mexida": f.atualizada[:16].replace("T", " "),
        "notas": f.notas[-3:],
    }
    return {k: v for k, v in d.items() if v not in ("", [], False)}


def ver(foco: Foco) -> dict[str, Any]:
    atual = foco.atual()
    return {
        "atual": _dict(atual) if atual else None,
        "ativas": [_dict(f) for f in foco.com_estado("ativa") if f is not atual],
        "travadas": [_dict(f) for f in foco.com_estado("bloqueada")],
        "pausadas": [_dict(f) for f in foco.com_estado("pausada")],
        "ideias": [f.titulo for f in foco.com_estado("ideia")],
        "concluidas_recentes": [
            f"{f.titulo} ({f.concluida_em[:10]})" for f in foco.com_estado("concluida")[:5]
        ],
        "limite_de_ativas": LIMITE,
    }


def ferramentas(foco: Foco) -> list[SdkMcpTool[Any]]:
    @tool(
        "foco_ver",
        "As frentes do usuário: a atual (no que ele estava), as ativas, travadas, pausadas, as "
        "ideias guardadas e as concluídas recentes. Fale no máximo três, a atual primeiro.",
        {},
    )
    async def _ver(_: dict[str, Any]) -> dict[str, Any]:
        return _texto(ver(foco))

    @tool(
        "foco_criar",
        "Anota uma frente que o usuário começou ou aprovou ('comecei X', 'vou fazer Y'), com o "
        f"próximo passo concreto se ele disse. Se já houver {LIMITE} ativas, ela entra pausada: "
        "diga isso e pergunte qual pausar. Projeto: o da sessão de código, se houver.",
        {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "proximo_passo": {"type": "string"},
                "projeto": {"type": "string"},
            },
            "required": ["titulo"],
        },
    )
    async def _criar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            f = foco.criar(
                str(args["titulo"]),
                str(args.get("proximo_passo", "")),
                str(args.get("projeto", "")),
            )
        except (FocoErro, KeyError) as erro:
            return _erro(erro)
        if f.estado == "pausada":
            ativas = ", ".join(x.titulo for x in foco.com_estado("ativa"))
            return _texto(
                f"Anotada como pausada: já há {LIMITE} ativas ({ativas}). Pergunte qual pausar."
            )
        return _texto(f"Anotada: {f.resumo()}" + (" É a frente atual." if f.atual else ""))

    @tool(
        "foco_atualizar",
        "Muda uma frente ou ideia que já existe: o próximo passo ('o próximo passo é…'), o que "
        "travou ('travei em…', vira travada), o estado (ativa, pausada, bloqueada, ideia; "
        "descartada para o que foi anotado por engano), o título (novo_titulo: uma correção ou um "
        "detalhe do mesmo assunto, como 'na verdade é perder dez quilos', muda o título; nunca "
        "crie outra) ou uma nota. Frente pelo nome, como ele falou.",
        {
            "type": "object",
            "properties": {
                "frente": {"type": "string"},
                "proximo_passo": {"type": "string"},
                "bloqueio": {"type": "string"},
                "estado": {
                    "type": "string",
                    "enum": ["ativa", "pausada", "bloqueada", "ideia", "descartada"],
                },
                "novo_titulo": {"type": "string"},
                "nota": {"type": "string"},
            },
            "required": ["frente"],
        },
    )
    async def _atualizar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            f = foco.atualizar(
                str(args["frente"]),
                args.get("proximo_passo"),
                args.get("bloqueio"),
                args.get("estado"),
                str(args.get("nota", "")),
                args.get("novo_titulo"),
            )
        except (FocoErro, KeyError) as erro:
            return _erro(erro)
        return _texto(f"Atualizada ({f.estado}): {f.resumo()}")

    @tool(
        "foco_focar",
        "Põe uma frente como a atual ('agora vou focar no X', 'volta para o Y'), ativando se "
        f"couber no limite de {LIMITE}.",
        {"frente": str},
    )
    async def _focar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            f = foco.focar(str(args["frente"]))
        except (FocoErro, KeyError) as erro:
            return _erro(erro)
        return _texto(f"Foco agora: {f.resumo()}")

    @tool(
        "foco_concluir",
        "Marca uma frente como feita ('terminei X'). O Zé comemora sozinho na tela; diga a "
        "próxima frente atual, se houver.",
        {"frente": str},
    )
    async def _concluir(args: dict[str, Any]) -> dict[str, Any]:
        try:
            f = foco.concluir(str(args["frente"]))
        except (FocoErro, KeyError) as erro:
            return _erro(erro)
        proxima = foco.atual()
        return _texto(
            f"Concluída: {f.titulo}."
            + (f" Próxima frente: {proxima.resumo()}." if proxima else " Nenhuma outra ativa.")
        )

    @tool(
        "foco_ideia",
        "Guarda uma ideia NOVA no estacionamento ('tive uma ideia…'), sem virar frente ativa nem "
        "tirar o foco do que ele está fazendo. Detalhe ou correção de uma ideia que já existe "
        "(a meta, a data, 'na verdade é…') não é ideia nova: use foco_atualizar com novo_titulo, "
        "juntando tudo num título só.",
        {"texto": str},
    )
    async def _ideia(args: dict[str, Any]) -> dict[str, Any]:
        try:
            f = foco.criar(str(args["texto"]), ideia=True)
        except (FocoErro, KeyError) as erro:
            return _erro(erro)
        return _texto(f"Ideia guardada: {f.titulo}. O foco continua onde estava.")

    @tool(
        "foco_juntar",
        "Junta anotações do mesmo assunto numa só ('isso é tudo a mesma coisa', ideias repetidas): "
        "mantém uma, com um título que resume tudo, e descarta as outras (ficam no histórico).",
        {
            "type": "object",
            "properties": {
                "manter": {"type": "string"},
                "outras": {"type": "array", "items": {"type": "string"}},
                "titulo": {"type": "string"},
            },
            "required": ["manter", "outras"],
        },
    )
    async def _juntar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            f = foco.juntar(
                str(args["manter"]),
                [str(x) for x in args.get("outras", [])],
                str(args.get("titulo", "")),
            )
        except (FocoErro, KeyError) as erro:
            return _erro(erro)
        return _texto(f"Juntadas em: {f.resumo()} ({f.estado}).")

    return [_ver, _criar, _atualizar, _focar, _concluir, _ideia, _juntar]


def servidor(foco: Foco) -> McpSdkServerConfig:
    return create_sdk_mcp_server(SERVIDOR, tools=ferramentas(foco))
