"""Ferramenta do modo manutenção: o cérebro liga ou desliga quando a frase escapou do comando local.

"Coloque no modo manutenção" chegou ao cérebro em 07/10/2026 e, sem ferramenta, ele abriu o menu
de configurações. Desde o ADR 0072, a fala comum nunca vai para a sessão de autodesenvolvimento:
o pedido a ela é explícito (`pedir`). Não é de leitura: passa pela aprovação falada (a frase vem
do laço).
"""

import asyncio
import time
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.oficina.manutencao import Manutencao


def ferramentas(manutencao: Manutencao | None) -> list[SdkMcpTool[Any]]:
    @tool(
        "modo_manutencao",
        "Liga ou desliga o modo manutenção, ou diz como está. Use quando ele pedir para entrar, "
        "ativar, colocar, sair ou desligar a manutenção, com qualquer palavra. Não é o menu de "
        "configurações. pedir: manda ao autodesenvolvimento (um agente de código no seu próprio "
        "repositório) a correção de uma falha sua, só quando o usuário pedir explicitamente "
        '("manda para o autodesenvolvimento corrigir...") ou responder a uma pergunta dele; '
        "pedido: o que corrigir, com o que deu errado. Funções novas e outros projetos não: são "
        "das sessões comuns. propor: publica no GitHub, num PR, as "
        'melhorias da cópia ("manda essa melhoria como PR", "salva no GitHub"), depois de '
        "conferir os testes e que não vai nenhum dado do usuário; sem isso, as melhorias ficam "
        "só nesta máquina.",
        {
            "type": "object",
            "properties": {
                "acao": {
                    "type": "string",
                    "enum": ["entrar", "sair", "situacao", "pedir", "propor"],
                },
                "pedido": {"type": "string"},
                "agente": {"type": "string", "enum": ["claude", "codex"]},
            },
            "required": ["acao"],
        },
    )
    async def modo_manutencao(args: dict[str, Any]) -> dict[str, Any]:
        if manutencao is None:
            return _erro(ValueError("modo manutenção indisponível"))
        acao = args.get("acao")
        if acao == "entrar":
            fala = await asyncio.to_thread(manutencao.entrar, str(args.get("agente") or ""))
        elif acao == "sair":
            fala = manutencao.sair()
        elif acao == "pedir":
            pedido = str(args.get("pedido") or "").strip()
            if not pedido:
                return _erro(ValueError("diga o que corrigir"))
            fala = await asyncio.to_thread(manutencao.pedir, pedido, time.time())
        elif acao == "propor":
            r = await asyncio.to_thread(manutencao.propor)
            return _texto({"publicado": r.ok, "diga": r.texto, "endereco": r.endereco})
        else:
            fala = manutencao.situacao(time.time())
        return _texto({"ligado": manutencao.ligado, "diga": fala})

    return [modo_manutencao]
