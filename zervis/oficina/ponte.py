"""A ponte dos conectores: o segredo fica com o Zé (plano de maturidade, Frente 2; ADR 0076).

Um conector com segredo (um token no ambiente, um cabeçalho de autorização, o login OAuth) ia
inteiro ao processo do agente: no ambiente do Codex, no arquivo de configuração do Claude. Um
`env` ou um `cat` bastava para o segredo ir ao modelo.

Agora o agente recebe só um endereço do Zé (`/sessoes/conectores/<nome>`, na porta do painel) e a
chave da própria sessão, a mesma do gancho de permissão: trocada a cada vez que o terminal abre,
sem valor depois que ele fecha (o escopo e o prazo). O Zé abre o conector de verdade, com o
segredo, na pasta do projeto, e repassa as ferramentas. As bloqueadas nem aparecem e, chamadas
direto, são recusadas aqui.

O servidor MCP é o do SDK oficial (sem estado, resposta em JSON): o painel entrega o pedido HTTP
inteiro e devolve a resposta. Cada conector aberto vive numa tarefa só (os cancel scopes do
cliente MCP) e fecha depois de 10 minutos sem uso, ou quando a sessão perde a chave.
"""

import asyncio
import contextlib
import logging
import threading
import time
from collections.abc import Awaitable, Callable, MutableMapping
from contextlib import AsyncExitStack
from dataclasses import replace
from pathlib import Path
from typing import Any

import mcp_types as types
from mcp import ClientSession
from mcp.server.lowlevel import Server
from mcp.server.transport_security import TransportSecuritySettings

from zervis.cerebro import mcp_externo
from zervis.cerebro.codex_mcp import abrir_transporte

log = logging.getLogger(__name__)

CAMINHO = "sessoes/conectores"
OCIOSA_S = 600.0
ABRIR_S = 30.0
CHAMAR_S = 120.0
VARRER_S = 60.0
CABECALHOS = ("accept", "content-type", "mcp-protocol-version", "mcp-session-id", "last-event-id")

Conectores = Callable[[str], tuple[mcp_externo.Externos, Path]]


class ConectorIndisponivel(RuntimeError):
    """O conector não existe para esta sessão, não leva segredo ou não abriu."""


def tem_segredo(config: dict[str, Any]) -> bool:
    return bool(config.get("env") or config.get("headers"))


class _Ligacao:
    """Um conector aberto para uma sessão. A sessão MCP mora numa tarefa só: quem pede manda o
    trabalho pela fila e espera o resultado."""

    def __init__(self, config: dict[str, Any], pasta: Path) -> None:
        self.config = config
        self.usada = time.monotonic()
        self.fila: asyncio.Queue[tuple[Callable[[ClientSession], Awaitable[Any]], Any]] = (
            asyncio.Queue()
        )
        self.pronta: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self.tarefa = asyncio.create_task(self._rodar(str(pasta)))

    @property
    def viva(self) -> bool:
        return not self.tarefa.done()

    async def _rodar(self, pasta: str) -> None:
        try:
            async with AsyncExitStack() as recursos:
                leitura, escrita = await abrir_transporte(recursos, self.config, pasta)
                sessao = await recursos.enter_async_context(
                    ClientSession(leitura, escrita, read_timeout_seconds=CHAMAR_S)
                )
                await sessao.initialize()
                self.pronta.set_result(None)
                while True:
                    trabalho, futuro = await self.fila.get()
                    if futuro.done():
                        continue
                    try:
                        resultado = await trabalho(sessao)
                    except Exception as erro:  # o erro vai a quem pediu, a ligação segue
                        if not futuro.done():
                            futuro.set_exception(erro)
                    else:
                        if not futuro.done():
                            futuro.set_result(resultado)
        except asyncio.CancelledError:
            raise
        except Exception as erro:
            if not self.pronta.done():
                self.pronta.set_exception(erro)
            else:
                log.warning("conector caiu: %s", erro)

    async def fazer(self, trabalho: Callable[[ClientSession], Awaitable[Any]]) -> Any:
        self.usada = time.monotonic()
        await asyncio.wait_for(asyncio.shield(self.pronta), ABRIR_S)
        if not self.viva:
            raise ConectorIndisponivel("o conector fechou")
        futuro: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        await self.fila.put((trabalho, futuro))
        return await asyncio.wait_for(futuro, CHAMAR_S)

    async def fechar(self) -> None:
        self.tarefa.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await self.tarefa


async def _todas_as_ferramentas(sessao: ClientSession) -> list[types.Tool]:
    ferramentas: list[types.Tool] = []
    cursor = None
    while True:
        lista = await sessao.list_tools(params=types.PaginatedRequestParams(cursor=cursor))
        ferramentas += lista.tools
        cursor = lista.next_cursor
        if not cursor:
            return ferramentas


class Ponte:
    def __init__(
        self,
        sessao_da_chave: Callable[[str], str | None],
        conectores: Conectores,
        tem_chave: Callable[[str], bool] = lambda _sessao: True,
    ) -> None:
        self.endereco = ""  # a rota no painel; vazio = sem painel, os segredos seguem diretos
        self._sessao_da_chave = sessao_da_chave
        self._conectores = conectores
        self._tem_chave = tem_chave
        self._ligacoes: dict[tuple[str, str], _Ligacao] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._vida: asyncio.Task[None] | None = None
        self._trava = threading.Lock()
        servidor = Server("ze-conectores", on_list_tools=self._listar, on_call_tool=self._chamar)
        self._app = servidor.streamable_http_app(
            streamable_http_path="/mcp",
            json_response=True,
            stateless_http=True,
            # O painel já confere o Host; aqui o pedido chega de dentro do próprio Zé.
            transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        )

    # --- para o agente -------------------------------------------------------------------------

    def para_agente(self, externos: mcp_externo.Externos, chave: str) -> mcp_externo.Externos:
        """Os conectores como o agente os vê: os que levam segredo trocados pela ponte."""
        if not self.endereco or not chave:
            return externos
        servidores = {
            nome: (
                {
                    "type": "http",
                    "url": f"{self.endereco}/{nome}",
                    "headers": {"Authorization": f"Bearer {chave}"},
                }
                if tem_segredo(config)
                else config
            )
            for nome, config in externos.servidores.items()
        }
        return replace(externos, servidores=servidores)

    # --- o pedido HTTP que o painel repassa ----------------------------------------------------

    def atender(
        self, metodo: str, nome: str, cabecalhos: dict[str, str], corpo: bytes
    ) -> tuple[int, list[tuple[str, str]], bytes]:
        autorizacao = cabecalhos.get("authorization", "")
        chave = autorizacao[7:] if autorizacao.startswith("Bearer ") else ""
        sessao = self._sessao_da_chave(chave) if chave else None
        if sessao is None:
            return 401, [("Content-Type", "application/json")], b'{"erro": "chave"}'
        repassar = [(k.encode(), v.encode()) for k, v in cabecalhos.items() if k in CABECALHOS]
        futuro = asyncio.run_coroutine_threadsafe(
            self._asgi(metodo, repassar, corpo, (sessao, nome)), self._em_pe()
        )
        return futuro.result(timeout=ABRIR_S + CHAMAR_S + 10)

    def _em_pe(self) -> asyncio.AbstractEventLoop:
        with self._trava:
            if self._loop is None:
                pronto = threading.Event()
                loop = asyncio.new_event_loop()

                def rodar() -> None:
                    asyncio.set_event_loop(loop)
                    self._vida = loop.create_task(self._viver(pronto))
                    loop.run_forever()

                threading.Thread(target=rodar, name="ponte-conectores", daemon=True).start()
                pronto.wait(10)
                self._loop = loop
            return self._loop

    async def _viver(self, pronto: threading.Event) -> None:
        async with self._app.router.lifespan_context(self._app):
            pronto.set()
            while True:
                await asyncio.sleep(VARRER_S)
                await self._varrer()

    async def _asgi(
        self,
        metodo: str,
        cabecalhos: list[tuple[bytes, bytes]],
        corpo: bytes,
        quem: tuple[str, str],
    ) -> tuple[int, list[tuple[str, str]], bytes]:
        respondido = asyncio.Event()
        entregue = False
        resposta: dict[str, Any] = {"status": 500, "headers": [], "corpo": b""}

        async def receber() -> dict[str, Any]:
            nonlocal entregue
            if not entregue:
                entregue = True
                return {"type": "http.request", "body": corpo, "more_body": False}
            await respondido.wait()
            return {"type": "http.disconnect"}

        async def enviar(mensagem: MutableMapping[str, Any]) -> None:
            if mensagem["type"] == "http.response.start":
                resposta["status"] = mensagem["status"]
                resposta["headers"] = mensagem.get("headers", [])
            elif mensagem["type"] == "http.response.body":
                resposta["corpo"] += mensagem.get("body", b"")
                if not mensagem.get("more_body"):
                    respondido.set()

        escopo = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": metodo,
            "scheme": "http",
            "path": "/mcp",
            "raw_path": b"/mcp",
            "query_string": b"",
            "root_path": "",
            "headers": [(b"host", b"127.0.0.1"), *cabecalhos],
            "client": ("127.0.0.1", 0),
            "server": ("127.0.0.1", 0),
            "state": {},
            "ze": quem,
        }
        await self._app(escopo, receber, enviar)
        respondido.set()
        saida = [(k.decode(), v.decode()) for k, v in resposta["headers"]]
        return int(resposta["status"]), saida, bytes(resposta["corpo"])

    # --- o servidor MCP ------------------------------------------------------------------------

    @staticmethod
    def _quem(ctx: Any) -> tuple[str, str]:
        sessao, nome = ctx.request.scope["ze"]
        return str(sessao), str(nome)

    async def _ligacao(self, sessao: str, nome: str) -> tuple[_Ligacao, list[str]]:
        externos, pasta = await asyncio.to_thread(self._conectores, sessao)
        config = externos.servidores.get(nome)
        if config is None or not tem_segredo(config):
            raise ConectorIndisponivel(f"conector {nome} não está ligado neste projeto")
        bloqueadas = [b for b in externos.bloqueadas if b.startswith(f"mcp__{nome}__")]
        atual = self._ligacoes.get((sessao, nome))
        if atual is not None and atual.viva and atual.config == config:
            return atual, bloqueadas
        if atual is not None:
            await atual.fechar()
        nova = _Ligacao(config, pasta)
        self._ligacoes[(sessao, nome)] = nova
        return nova, bloqueadas

    async def _listar(self, ctx: Any, _params: Any) -> types.ListToolsResult:
        sessao, nome = self._quem(ctx)
        ligacao, bloqueadas = await self._ligacao(sessao, nome)
        ferramentas = await ligacao.fazer(_todas_as_ferramentas)
        return types.ListToolsResult(
            tools=[f for f in ferramentas if f"mcp__{nome}__{f.name}" not in bloqueadas]
        )

    async def _chamar(self, ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        sessao, nome = self._quem(ctx)
        ligacao, bloqueadas = await self._ligacao(sessao, nome)
        if f"mcp__{nome}__{params.name}" in bloqueadas:
            return types.CallToolResult(
                content=[types.TextContent(text="Ferramenta bloqueada neste conector.")],
                is_error=True,
            )
        argumentos = params.arguments or {}
        resultado: types.CallToolResult = await ligacao.fazer(
            lambda s: s.call_tool(params.name, argumentos)
        )
        return resultado

    async def _varrer(self) -> None:
        """Fecha o que ficou parado e o que é de uma sessão sem chave (o terminal fechou)."""
        agora = time.monotonic()
        for quem, ligacao in list(self._ligacoes.items()):
            parada = agora - ligacao.usada > OCIOSA_S
            if parada or not ligacao.viva or not self._tem_chave(quem[0]):
                del self._ligacoes[quem]
                await ligacao.fechar()

    def parar(self) -> None:
        with self._trava:
            loop, self._loop = self._loop, None
        if loop is None:
            return

        async def fechar_tudo() -> None:
            for ligacao in list(self._ligacoes.values()):
                await ligacao.fechar()
            self._ligacoes.clear()

        with contextlib.suppress(Exception):
            asyncio.run_coroutine_threadsafe(fechar_tudo(), loop).result(timeout=10)
        loop.call_soon_threadsafe(loop.stop)
