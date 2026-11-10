"""Entrada de fora (plano de maturidade, Frente 2): depois de ler texto de terceiros, o turno
não executa nada sem a aprovação falada do usuário."""

import asyncio
from pathlib import Path
from typing import Any

from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

from zervis.cerebro import ferramentas
from zervis.cerebro.base import Resposta
from zervis.cerebro.claude import ClaudeBrain

LEMBRETE = "mcp__jarvis__automacao_lembrete"
SISTEMA = "mcp__jarvis__sistema_executar"
ROLAR = "mcp__navegador__browser_press_key"


def _cerebro(tmp_path: Path, perguntas: list[str], sim: bool) -> ClaudeBrain:
    b = ClaudeBrain(
        "x",
        [],
        tmp_path,
        livres=[*ferramentas.LIVRES],
        autoaprovar=lambda nome, _e: nome in (SISTEMA, ROLAR),  # risco baixo e rolar
        autoaprovar_de_fora=lambda nome, _e: nome == ROLAR,
        de_fora=ferramentas.de_fora,
        com_efeito=ferramentas.COM_EFEITO,
    )

    async def aprovar(descricao: str) -> Resposta:
        perguntas.append(descricao)
        return Resposta(sim)

    b.aprovar = aprovar
    return b


def test_de_onde_vem_o_texto_de_terceiros() -> None:
    assert ferramentas.de_fora("mcp__jarvis__whatsapp_ler") == "uma conversa do WhatsApp"
    assert ferramentas.de_fora("mcp__jarvis__sessoes_listar") == ""  # do próprio Zé
    assert ferramentas.de_fora("mcp__n8n-loja__executar") == "o conector n8n-loja"
    assert ferramentas.de_fora("WebFetch") == "uma página da internet"
    assert ferramentas.de_fora("Bash") == ""
    # Toda fonte de fora e toda livre com efeito estão na lista das livres.
    assert set(ferramentas.DE_FORA) <= set(ferramentas.LEITURA)
    assert set(ferramentas.LIVRES) >= ferramentas.COM_EFEITO


def test_turno_limpo_a_politica_libera_e_a_livre_nao_pergunta(tmp_path: Path) -> None:
    perguntas: list[str] = []
    b = _cerebro(tmp_path, perguntas, sim=False)
    assert not b.precisa_perguntar(LEMBRETE)
    decisao = asyncio.run(b._pode_usar(SISTEMA, {}, None))  # type: ignore[arg-type]
    assert isinstance(decisao, PermissionResultAllow) and perguntas == []


def test_turno_de_fora_tudo_que_muda_algo_pede_o_sim(tmp_path: Path) -> None:
    perguntas: list[str] = []
    b = _cerebro(tmp_path, perguntas, sim=False)
    b.viu("mcp__jarvis__sessoes_listar")  # do próprio Zé: segue limpo
    assert b.fonte_de_fora == ""
    b.viu("mcp__jarvis__pagina_ler")
    b.viu("mcp__jarvis__whatsapp_ler")  # a primeira fonte fica
    assert b.fonte_de_fora == "uma página da internet"
    assert b.precisa_perguntar(LEMBRETE)  # livre com efeito
    assert not b.precisa_perguntar("mcp__jarvis__whatsapp_conversas")  # só lê
    # A política de risco não libera sozinha; rolar a página continua livre.
    decisao = asyncio.run(b._pode_usar(SISTEMA, {}, None))  # type: ignore[arg-type]
    assert isinstance(decisao, PermissionResultDeny) and len(perguntas) == 1
    assert isinstance(asyncio.run(b._pode_usar(ROLAR, {}, None)), PermissionResultAllow)  # type: ignore[arg-type]
    assert len(perguntas) == 1


def _antes(b: ClaudeBrain, nome: str) -> dict[str, Any]:
    entrada: Any = {"hook_event_name": "PreToolUse", "tool_name": nome, "tool_input": {}}
    return dict(asyncio.run(b._antes_da_ferramenta(entrada, None, None)))  # type: ignore[arg-type]


def test_no_claude_o_gancho_pergunta_pela_livre_com_efeito(tmp_path: Path) -> None:
    perguntas: list[str] = []
    b = _cerebro(tmp_path, perguntas, sim=False)
    assert _antes(b, LEMBRETE) == {} and perguntas == []  # turno limpo: livre
    b.viu("mcp__jarvis__whatsapp_ler")
    negado = _antes(b, LEMBRETE)
    assert negado["hookSpecificOutput"]["permissionDecision"] == "deny" and len(perguntas) == 1
    assert _antes(b, "mcp__jarvis__whatsapp_conversas") == {}  # ler segue livre
    sim = _cerebro(tmp_path, [], sim=True)
    sim.viu("mcp__jarvis__whatsapp_ler")
    assert _antes(sim, LEMBRETE) == {}  # aprovado pela voz: segue
