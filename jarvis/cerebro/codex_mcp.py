"""As mesmas ferramentas MCP do Claude, servidas às chamadas dinâmicas do Codex."""

import asyncio
import contextlib
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, types
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.shared.memory import create_client_server_memory_streams


class FerramentasCodex:
    def __init__(self, servidores: dict[str, Any], bloqueadas: list[str]) -> None:
        self.servidores, self.bloqueadas = servidores, set(bloqueadas)
        self.definicoes: list[dict[str, Any]] = []
        self.alvos: dict[str, tuple[ClientSession, str]] = {}
        self.apelidos: dict[str, str] = {}  # O prefixo mcp__ é reservado no app-server.
        self.fila: asyncio.Queue[tuple[str, dict[str, Any], asyncio.Future[Any]]] = asyncio.Queue()
        self.pronto: asyncio.Future[None] | None = None
        self.tarefa: asyncio.Task[None] | None = None

    async def iniciar(self) -> None:
        self.pronto = asyncio.get_running_loop().create_future()
        self.tarefa = asyncio.create_task(self._rodar())
        await asyncio.wait_for(asyncio.shield(self.pronto), 20)

    async def _rodar(self) -> None:
        # As sessões MCP e seus cancel scopes são abertos e fechados na mesma tarefa.
        try:
            async with AsyncExitStack() as recursos:
                for nome, cfg in self.servidores.items():
                    leitura: Any
                    escrita: Any
                    if cfg["type"] == "sdk":
                        cliente, servidor = await recursos.enter_async_context(
                            create_client_server_memory_streams()
                        )
                        instancia = cfg["instance"]
                        tarefa = asyncio.create_task(
                            instancia.run(*servidor, instancia.create_initialization_options())
                        )
                        recursos.push_async_callback(self._parar, tarefa)
                        leitura, escrita = cliente
                    elif cfg["type"] == "stdio":
                        leitura, escrita = await recursos.enter_async_context(
                            stdio_client(
                                StdioServerParameters(
                                    command=cfg["command"],
                                    args=cfg.get("args", []),
                                    env=cfg.get("env"),
                                )
                            )
                        )
                    elif cfg["type"] == "sse":
                        leitura, escrita = await recursos.enter_async_context(
                            sse_client(cfg["url"], headers=cfg.get("headers"), sse_read_timeout=120)
                        )
                    elif cfg["type"] == "http":
                        http = await recursos.enter_async_context(
                            create_mcp_http_client(headers=cfg.get("headers"))
                        )
                        leitura, escrita = await recursos.enter_async_context(
                            streamable_http_client(cfg["url"], http_client=http)
                        )
                    else:
                        raise ValueError("Transporte MCP não suportado.")
                    sessao = await recursos.enter_async_context(
                        ClientSession(leitura, escrita, read_timeout_seconds=120)
                    )
                    await sessao.initialize()
                    cursor = None
                    while True:
                        lista = await sessao.list_tools(
                            params=types.PaginatedRequestParams(cursor=cursor)
                        )
                        for ferramenta in lista.tools:
                            chave = f"mcp__{nome}__{ferramenta.name}"
                            if chave in self.bloqueadas:
                                continue
                            self.alvos[chave] = (sessao, ferramenta.name)
                            apelido = f"ze__{nome}__{ferramenta.name}"
                            self.apelidos[apelido] = chave
                            self.definicoes.append(
                                {
                                    "type": "function",
                                    "name": apelido,
                                    "description": ferramenta.description or ferramenta.name,
                                    "inputSchema": ferramenta.input_schema,
                                }
                            )
                        cursor = lista.next_cursor
                        if not cursor:
                            break
                if self.pronto is not None and not self.pronto.done():
                    self.pronto.set_result(None)
                while True:
                    nome, argumentos, futuro = await self.fila.get()
                    if futuro.cancelled():
                        continue
                    try:
                        sessao, ferramenta_nome = self.alvos[nome]
                        resultado = await sessao.call_tool(ferramenta_nome, argumentos)
                        if not futuro.done():
                            futuro.set_result(resultado)
                    except Exception as erro:
                        if not futuro.done():
                            futuro.set_exception(erro)
        except asyncio.CancelledError:
            raise
        except Exception as erro:
            if self.pronto is not None and not self.pronto.done():
                self.pronto.set_exception(erro)
            else:
                raise

    @staticmethod
    async def _parar(tarefa: asyncio.Task[None]) -> None:
        tarefa.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarefa

    async def chamar(self, nome: str, argumentos: dict[str, Any]) -> Any:
        futuro: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        await self.fila.put((nome, argumentos, futuro))
        return await asyncio.wait_for(futuro, 120)

    async def fechar(self) -> None:
        if self.tarefa is not None:
            await self._parar(self.tarefa)
        self.tarefa = None
        self.definicoes.clear()
        self.alvos.clear()
        self.apelidos.clear()
