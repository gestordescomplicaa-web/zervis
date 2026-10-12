"""Cliente do app-server oficial do Codex: RPC por stdio, sem expor o servidor na rede."""

import asyncio
import contextlib
import json
import os
import signal
import tomllib
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from jarvis.cerebro.contas import Conta


class CodexErro(RuntimeError):
    """Código de falha para o núcleo, sem credenciais ou conteúdo de conversa."""


def codigo_erro(erro: Any) -> str:
    info = erro.get("codexErrorInfo", "") if isinstance(erro, dict) else str(erro)
    texto = json.dumps(erro, ensure_ascii=False).lower()
    if info in ("usageLimitExceeded", "rateLimitExceeded", "sessionBudgetExceeded") or any(
        x in texto for x in ("usage limit", "session limit", "rate limit", "insufficient_quota")
    ):
        return "limite_de_uso"
    if info == "unauthorized" or any(x in texto for x in ("unauthorized", "not logged in")):
        return "acesso_invalido"
    return "falha_codex"


def comando(conta: Conta) -> list[str]:
    # A voz e o cérebro só usam as ferramentas publicadas pelo Zérvis, com sua autorização.
    cfg: dict[str, Any] = {
        "features.shell_tool": False,
        "features.unified_exec": False,
        "features.multi_agent": False,
        "features.multi_agent_v2": False,
        "features.apps": False,
        "features.browser_use": False,
        "features.computer_use": False,
        "features.image_generation": False,
        "features.view_image": False,
        "features.code_mode": False,
        # O CLI encaminha ferramentas dinâmicas por este host, inclusive sem code_mode.
        "features.code_mode_host": True,
        "features.goals": False,
        "web_search": "disabled",
        "project_doc_max_bytes": 0,
    }
    try:
        dados = tomllib.loads((conta.onde / "config.toml").read_text())
    except (OSError, tomllib.TOMLDecodeError):
        dados = {}
    for nome in dados.get("mcp_servers", {}):
        cfg[f"mcp_servers.{json.dumps(nome)}.enabled"] = False
    return [
        "codex",
        "app-server",
        *[a for k, v in cfg.items() for a in ("-c", f"{k}={json.dumps(v)}")],
    ]


class ClienteCodex:
    def __init__(
        self,
        conta: Conta,
        pasta: Path,
        ao_evento: Callable[[str, dict[str, Any]], None],
        atender: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> None:
        self.conta, self.pasta = conta, pasta
        self.ao_evento, self.atender = ao_evento, atender
        self.processo: asyncio.subprocess.Process | None = None
        self.leitor: asyncio.Task[None] | None = None
        self.pendentes: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self.chamadas: set[asyncio.Task[None]] = set()
        self.numero = 0
        self.escrita = asyncio.Lock()

    async def iniciar(self) -> None:
        ambiente = dict(os.environ)
        ambiente["CODEX_HOME"] = str(self.conta.onde)
        self.processo = await asyncio.create_subprocess_exec(
            *comando(self.conta),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=self.pasta,
            env=ambiente,
            start_new_session=True,
            limit=2 * 1024 * 1024,
        )
        self.leitor = asyncio.create_task(self._ler())
        await self.pedir(
            "initialize",
            {
                "clientInfo": {"name": "zervis", "title": "Zérvis", "version": "0.0.1"},
                "capabilities": {"experimentalApi": True},
            },
        )
        await self._enviar({"method": "initialized"})

    async def _enviar(self, mensagem: dict[str, Any]) -> None:
        if self.processo is None or self.processo.stdin is None:
            raise CodexErro("transporte_encerrado")
        async with self.escrita:
            self.processo.stdin.write((json.dumps(mensagem, ensure_ascii=False) + "\n").encode())
            await self.processo.stdin.drain()

    async def pedir(
        self, metodo: str, params: dict[str, Any], espera_s: float = 20.0
    ) -> dict[str, Any]:
        self.numero += 1
        id_ = self.numero
        futuro: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self.pendentes[id_] = futuro
        try:
            await self._enviar({"id": id_, "method": metodo, "params": params})
            return await asyncio.wait_for(futuro, espera_s)
        finally:
            self.pendentes.pop(id_, None)

    async def _responder(self, mensagem: dict[str, Any]) -> None:
        try:
            resultado = await self.atender(mensagem["method"], mensagem.get("params", {}))
            await self._enviar({"id": mensagem["id"], "result": resultado})
        except asyncio.CancelledError:
            raise
        except Exception:
            with contextlib.suppress(Exception):
                await self._enviar(
                    {"id": mensagem["id"], "error": {"code": -32603, "message": "Pedido recusado."}}
                )

    async def _ler(self) -> None:
        if self.processo is None or self.processo.stdout is None:
            raise CodexErro("transporte_encerrado")
        try:
            while linha := await self.processo.stdout.readline():
                mensagem = json.loads(linha)
                if not isinstance(mensagem, dict):
                    continue
                if "method" in mensagem:
                    if "id" in mensagem:
                        tarefa = asyncio.create_task(self._responder(mensagem))
                        self.chamadas.add(tarefa)
                        tarefa.add_done_callback(self.chamadas.discard)
                    else:
                        self.ao_evento(mensagem["method"], mensagem.get("params", {}))
                elif (futuro := self.pendentes.get(mensagem.get("id", -1))) and not futuro.done():
                    if "error" in mensagem:
                        futuro.set_exception(CodexErro(codigo_erro(mensagem["error"])))
                    else:
                        futuro.set_result(mensagem.get("result", {}))
        finally:
            for futuro in self.pendentes.values():
                if not futuro.done():
                    futuro.set_exception(CodexErro("transporte_encerrado"))
            self.ao_evento("transporte_encerrado", {})

    async def fechar(self) -> None:
        for tarefa in self.chamadas:
            tarefa.cancel()
        if self.chamadas:
            await asyncio.gather(*self.chamadas, return_exceptions=True)
        if self.processo is not None and self.processo.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.processo.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(self.processo.wait(), 5)
            except TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(self.processo.pid, signal.SIGKILL)
                await asyncio.wait_for(self.processo.wait(), 5)
        if self.leitor is not None:
            self.leitor.cancel()
            with contextlib.suppress(asyncio.CancelledError, ValueError, OSError):
                await self.leitor
        self.processo = None
