"""ClaudeBrain sem rede: carimbo de data, descrição falada e tempo limite."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

import pytest

from zervis.cerebro.base import EventoCerebro, Fim
from zervis.cerebro.claude import FUSO, ClaudeBrain, carimbo, descrever


def test_carimbo_em_portugues_no_fuso_de_recife() -> None:
    assert carimbo(datetime(2026, 10, 6, 14, 5, tzinfo=FUSO)) == "[terça-feira, 06/10/2026, 14:05]"


def test_descricoes_faladas_das_ferramentas() -> None:
    assert descrever("WebSearch", {"query": "previsão do tempo"}) == (
        "Vou pesquisar na internet: previsão do tempo."
    )
    assert descrever("WebFetch", {"url": "https://www.example.com/a?b=1"}) == (
        "Vou abrir a página example.com."
    )
    assert descrever("Bash", {"command": "rm -rf /"}) == "Vou usar a ferramenta Bash."


class ClienteMudo:
    """Aceita o pedido e nunca responde, como um provedor travado."""

    async def query(self, texto: str) -> None:
        pass

    async def receive_response(self) -> AsyncIterator[object]:
        await asyncio.sleep(3600)
        yield None

    async def disconnect(self) -> None:
        pass


def test_sem_resposta_no_prazo_falha_e_refaz_a_sessao(tmp_path: Path) -> None:
    cerebro = ClaudeBrain("m", [], tmp_path, tempo_limite_s=0.05)
    cerebro.cliente = ClienteMudo()  # type: ignore[assignment]

    async def rodar() -> list[EventoCerebro]:
        return [evento async for evento in cerebro.ask("oi")]

    assert asyncio.run(rodar()) == [Fim(erro="tempo_esgotado")]
    assert cerebro.cliente is None


def test_conta_as_ferramentas_usadas_na_resposta(tmp_path: Path) -> None:
    from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock

    cerebro = ClaudeBrain("m", [], tmp_path)
    msg = AssistantMessage(
        content=[
            TextBlock("Vou ver."),
            ToolUseBlock(id="1", name="mcp__jarvis__sistema_estado", input={}),
        ],
        model="claude-sonnet-5-5",
    )
    cerebro._traduzir(msg)
    cerebro._traduzir(msg)
    assert cerebro.ferramentas_usadas == ["mcp__jarvis__sistema_estado"] * 2


def test_o_gancho_depois_troca_a_resposta_que_o_modelo_ve(tmp_path: Path) -> None:
    vistas: list[tuple[str, object]] = []

    def depois(nome: str, resposta: object) -> object | None:
        vistas.append((nome, resposta))
        return "curta" if nome.startswith("mcp__navegador__") else None

    cerebro = ClaudeBrain("m", [], tmp_path, depois=depois)
    assert cerebro.opcoes().hooks is not None
    # Sem `depois`, o gancho continua: ele registra os MCPs externos na Atividade.
    assert ClaudeBrain("m", [], tmp_path).opcoes().hooks is not None

    def rodar(nome: str) -> object:
        entrada = {"hook_event_name": "PostToolUse", "tool_name": nome, "tool_response": "longa"}
        return asyncio.run(cerebro._depois_da_ferramenta(entrada, "id", {"signal": None}))  # type: ignore[arg-type]

    assert rodar("mcp__navegador__browser_snapshot") == {
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedMCPToolOutput": "curta"}
    }
    assert rodar("mcp__jarvis__tela_ver") == {}
    assert vistas[0] == ("mcp__navegador__browser_snapshot", "longa")


def test_limite_real_com_subtipo_success_continua_sendo_erro(tmp_path: Path) -> None:
    from claude_agent_sdk import AssistantMessage, ResultMessage

    brain = ClaudeBrain("m", [], tmp_path)
    brain._traduzir(AssistantMessage(content=[], model="m", error="rate_limit"))
    msg = ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=True,
        num_turns=1,
        session_id="teste",
        result="You've hit your session limit",
    )
    assert brain._traduzir(msg) == Fim("limite_de_uso")


def test_ferramenta_de_conector_vai_para_a_atividade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O cérebro usou o n8n pela conversa e nada apareceu na Atividade (19/10/2026)."""
    from zervis import atividade

    registro = atividade.Atividade(tmp_path / "atividade.jsonl")
    monkeypatch.setattr(atividade, "PADRAO", registro)
    registro.autorizada("mcp__n8n-teste__search_workflows", "aprovada")
    cerebro = ClaudeBrain("m", [], tmp_path)
    for nome, resposta in (
        ("mcp__n8n-teste__search_workflows", [{"type": "text", "text": "2 fluxos"}]),
        ("mcp__jarvis__tela_ver", [{"type": "text", "text": "a tela"}]),  # registro próprio
    ):
        entrada = {"hook_event_name": "PostToolUse", "tool_name": nome,
                   "tool_input": {"query": "pedidos"}, "tool_response": resposta}  # fmt: skip
        asyncio.run(cerebro._depois_da_ferramenta(entrada, "id", {"signal": None}))  # type: ignore[arg-type]
    (linha,) = registro.listar()
    assert (linha["tipo"], linha["ferramenta"], linha["autorizacao"], linha["resultado"]) == (
        "execucao",
        "mcp__n8n-teste__search_workflows",
        "aprovada",
        "2 fluxos",
    )
    assert linha["entrada"] == {"query": "pedidos"}
