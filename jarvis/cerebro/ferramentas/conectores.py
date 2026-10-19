"""Ferramentas dos conectores MCP (ADR 0037): o Zé integra um sistema novo sem sair da conversa.

Listar e testar passam sem perguntar: só leem o que já está cadastrado (o teste sobe o servidor
que a pessoa aprovou ao cadastrar). Cadastrar pede a aprovação falada, com o comando ou o endereço
na frase. Segredo nunca entra por aqui: o cérebro só dá os nomes das variáveis, e a pessoa guarda
o valor no painel (Conectores). O conector cadastrado vale para o cérebro depois de "Aplicar
agora" no painel, que remonta a conversa com ele.
"""

import asyncio
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from jarvis.cerebro import conectores, mcp_externo
from jarvis.cerebro.ferramentas.comum import _erro, _texto
from jarvis.cerebro.mcp_externo import McpInvalido

APLICAR = "Para valer na conversa, a pessoa aplica em Conectores (Aplicar agora)."


def _dados(args: dict[str, Any]) -> dict[str, Any]:
    """Só os campos do conector, nos tipos que o painel grava."""
    listas = ("argumentos", "ambiente", "livres", "bloqueadas", "projetos")
    dados: dict[str, Any] = {k: args[k] for k in listas if isinstance(args.get(k), list)}
    for chave in ("tipo", "comando", "url"):
        if isinstance(args.get(chave), str):
            dados[chave] = args[chave]
    if isinstance(args.get("cabecalhos"), dict):
        dados["cabecalhos"] = args["cabecalhos"]
    if args.get("oauth") is True:
        dados["oauth"] = True
    return dados


def _listar() -> list[dict[str, Any]]:
    return conectores.listar(mcp_externo.CAMINHO, mcp_externo.PAINEL)


def _testar(nome: str) -> dict[str, Any]:
    return conectores.testar(nome, mcp_externo.CAMINHO, mcp_externo.PAINEL)


def _salvar(nome: str, dados: dict[str, Any]) -> None:
    conectores.salvar(nome, dados, mcp_externo.PAINEL, mcp_externo.CAMINHO)


def ferramentas() -> list[SdkMcpTool[Any]]:
    @tool(
        "conectores_listar",
        "Os conectores MCP do Zé (ligações com outros sistemas): nome, tipo, comando ou "
        "endereço, se está ligado e quais segredos faltam (só os nomes, nunca os valores).",
        {},
    )
    async def conectores_listar(_: dict[str, Any]) -> dict[str, Any]:
        try:
            lista = await asyncio.to_thread(_listar)
        except McpInvalido as erro:
            return _erro(erro)
        resumo = [
            {
                "nome": c["nome"],
                "tipo": "remoto" if c["tipo"] == "http" else "local",
                "onde": c["url"] or " ".join([c["comando"], *c["argumentos"]]),
                "ligado": c["ligado"],
                "faltam_segredos": [v for v, tem in c["segredos"].items() if not tem],
                "projetos": c["projetos"],
                "origem": c["origem"],
            }
            for c in lista
        ]
        return _texto(resumo or "Nenhum conector cadastrado.")

    @tool(
        "conector_testar",
        "Sobe um conector cadastrado e lista as ferramentas dele: a prova de que a conexão "
        "funciona. Use depois de cadastrar e quando a pessoa disser que guardou o segredo.",
        {"nome": str},
    )
    async def conector_testar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            resultado = await asyncio.to_thread(_testar, str(args.get("nome", "")))
        except McpInvalido as erro:
            return _erro(erro)
        return _texto(resultado)

    @tool(
        "conector_cadastrar",
        "Cadastra (ou troca) um conector MCP do painel. Siga a skill integrar-sistema. tipo "
        "'stdio' (comando e argumentos de um servidor local) ou 'http' (url https de um "
        "servidor remoto). Segredos: só os NOMES das variáveis, em MAIÚSCULAS (ambiente, para o "
        "stdio; cabecalhos = {Cabeçalho: VARIAVEL}, para o http); nunca o valor, nem em "
        "argumentos ou na url. oauth = true para um MCP remoto que pede login (a pessoa entra "
        "pelo painel; sem segredos próprios). livres = ferramentas só de leitura, sem pergunta; "
        "bloqueadas = as que apagam ou fazem o que a pessoa não quer. O resto pede aprovação. "
        "projetos = nomes das pastas dos projetos cujas sessões de código também usam o "
        "conector ('*' = todos; vazio = só a conversa); o de um cliente só nos projetos dele. A "
        "pessoa aprova por voz.",
        {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "minúsculas, números e hífen"},
                "tipo": {"type": "string", "enum": ["stdio", "http"]},
                "comando": {"type": "string"},
                "argumentos": {"type": "array", "items": {"type": "string"}},
                "url": {"type": "string"},
                "ambiente": {"type": "array", "items": {"type": "string"}},
                "cabecalhos": {"type": "object", "additionalProperties": {"type": "string"}},
                "livres": {"type": "array", "items": {"type": "string"}},
                "bloqueadas": {"type": "array", "items": {"type": "string"}},
                "projetos": {"type": "array", "items": {"type": "string"}},
                "oauth": {"type": "boolean"},
            },
            "required": ["nome", "tipo"],
        },
    )
    async def conector_cadastrar(args: dict[str, Any]) -> dict[str, Any]:
        nome = str(args.get("nome", "")).strip()
        try:
            await asyncio.to_thread(_salvar, nome, _dados(args))
            listado = next(c for c in await asyncio.to_thread(_listar) if c["nome"] == nome)
        except McpInvalido as erro:
            return _erro(erro)
        if listado["oauth"] and not listado["conectado"]:
            return _texto(
                {
                    "cadastrado": nome,
                    "proximo_passo": f"A pessoa clica em Entrar no cartão {nome}, em Conectores, "
                    f"e faz o login no navegador; depois teste com conector_testar. {APLICAR}",
                }
            )
        faltam = [v for v, tem in listado["segredos"].items() if not tem]
        if faltam:
            return _texto(
                {
                    "cadastrado": nome,
                    "faltam_segredos": faltam,
                    "proximo_passo": "A pessoa guarda o valor de cada segredo em Conectores, no "
                    f"cartão {nome}; depois teste com conector_testar. {APLICAR}",
                }
            )
        teste = await asyncio.to_thread(_testar, nome)
        return _texto({"cadastrado": nome, "teste": teste, "proximo_passo": APLICAR})

    return [conectores_listar, conector_testar, conector_cadastrar]
