"""Codex: protocolo, cotas e mesmas autorizações das ferramentas do Zérvis."""

import asyncio
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from jarvis.cerebro.base import Fim, Texto
from jarvis.cerebro.codex import CodexBrain
from jarvis.cerebro.codex_mcp import FerramentasCodex
from jarvis.cerebro.codex_rpc import codigo_erro


def test_erros_de_cota_e_login_sao_codigos_sem_conteudo() -> None:
    assert codigo_erro({"codexErrorInfo": "usageLimitExceeded"}) == "limite_de_uso"
    assert codigo_erro({"codexErrorInfo": "unauthorized"}) == "acesso_invalido"
    assert codigo_erro({"message": "texto privado"}) == "falha_codex"


def test_ferramenta_real_mcp_exige_aprovacao_e_respeita_bloqueio(tmp_path: Path) -> None:
    chamadas: list[int] = []

    @tool("somar", "Soma dois números", {"a": int, "b": int})
    async def somar(args: dict[str, Any]) -> dict[str, Any]:
        chamadas.append(args["a"] + args["b"])
        return {"content": [{"type": "text", "text": str(chamadas[-1])}]}

    async def rodar() -> None:
        cfg = {"teste": create_sdk_mcp_server(name="teste", tools=[somar])}
        ponte = FerramentasCodex(cfg, [])
        brain = CodexBrain("", [], tmp_path)
        brain.fio, brain.turno, brain.ponte_mcp = "fio", "turno", ponte
        dados = {
            "threadId": "fio",
            "turnId": "turno",
            "tool": "ze__teste__somar",
            "arguments": {"a": 2, "b": 3},
        }
        try:
            await ponte.iniciar()
            assert ponte.definicoes[0]["inputSchema"]["properties"]["a"]["type"] == "integer"
            negado = await brain._atender_codex("item/tool/call", dados)
            assert not negado["success"] and chamadas == []
            brain.autoaprovar = lambda nome, args: True
            permitido = await brain._atender_codex("item/tool/call", dados)
            assert permitido == {
                "success": True,
                "contentItems": [{"type": "inputText", "text": "5"}],
            }
            assert chamadas == [5]
            dados["turnId"] = "outro"
            assert not (await brain._atender_codex("item/tool/call", dados))["success"]
            assert chamadas == [5]
            assert await brain._atender_codex("item/commandExecution/requestApproval", {}) == {
                "decision": "decline"
            }
        finally:
            await brain.close()
        bloqueada = FerramentasCodex(cfg, ["mcp__teste__somar"])
        try:
            await bloqueada.iniciar()
            assert bloqueada.definicoes == [] and bloqueada.alvos == {}
        finally:
            await bloqueada.fechar()

    asyncio.run(rodar())


class RpcFluxo:
    def __init__(self, brain: CodexBrain) -> None:
        self.brain = brain
        self.interrompido = False

    async def pedir(
        self, metodo: str, dados: dict[str, Any], espera_s: float = 20
    ) -> dict[str, Any]:
        if metodo == "turn/interrupt":
            self.interrompido = True
            return {}
        self.brain._evento_codex("turn/started", {"threadId": "fio", "turn": {"id": "turno"}})
        self.brain._evento_codex(
            "turn/completed", {"threadId": "fio", "turn": {"id": "antigo", "status": "failed"}}
        )
        self.brain._evento_codex(
            "item/agentMessage/delta", {"threadId": "outro", "turnId": "turno", "delta": "segredo"}
        )
        self.brain._evento_codex(
            "item/agentMessage/delta", {"threadId": "fio", "turnId": "turno", "delta": "5"}
        )
        self.brain._evento_codex(
            "thread/tokenUsage/updated",
            {
                "threadId": "fio",
                "tokenUsage": {
                    "last": {"inputTokens": 100, "cachedInputTokens": 80, "outputTokens": 1}
                },
            },
        )
        self.brain._evento_codex(
            "turn/completed", {"threadId": "fio", "turn": {"id": "turno", "status": "completed"}}
        )
        return {"turn": {"id": "turno"}}


def test_fluxo_isola_fio_e_conta_cache_sem_duplicar(tmp_path: Path) -> None:
    brain = CodexBrain("", [], tmp_path)
    brain.fio = "fio"
    brain.rpc = RpcFluxo(brain)  # type: ignore[assignment]

    async def rodar() -> None:
        assert [e async for e in brain.ask("2+3")] == [Texto("5"), Fim()]
        assert brain.uso == {
            "input_tokens": 20,
            "cache_read_input_tokens": 80,
            "cache_creation_input_tokens": 0,
            "output_tokens": 1,
        }
        assert not brain.assinatura

    asyncio.run(rodar())
