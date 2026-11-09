"""Os motores da via rápida (`zervis/cerebro/rapido.py`): o HTTP no formato da OpenAI e da
Anthropic, o Claude e o Codex pela assinatura e a lista de contas, com uma conexão que fica
aberta entre pedidos. Tirados de `rapido.py`, que continua exportando os nomes."""

import asyncio
import contextlib
import http.client
import json
import logging
import os
import socket
import threading
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from zervis.cerebro import contas
from zervis.cerebro.base import Texto
from zervis.cerebro.claude import ClaudeBrain
from zervis.cerebro.codex import CodexBrain

# O mesmo nome de antes: o registro do serviço continua igual.
log = logging.getLogger("zervis.cerebro.rapido")
ENDERECOS = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "anthropic": "https://api.anthropic.com/v1",
}
_FIM = object()


class MotorErro(RuntimeError):
    pass


class Motor(Protocol):
    nome: str
    com_estado: bool  # guarda a conversa sozinho (só recebe o que perdeu)

    @property
    def modelo(self) -> str: ...

    @property
    def uso(self) -> dict[str, Any] | None: ...

    async def iniciar(self, sistema: str) -> None: ...
    def gerar(self, sistema: str, mensagens: list[dict[str, str]]) -> AsyncIterator[str]: ...
    async def interromper(self) -> None: ...
    async def reiniciar(self) -> None: ...
    async def fechar(self) -> None: ...


class Http:
    """Uma conexão persistente e a leitura em fluxo numa thread, linha a linha."""

    def __init__(self, base: str, tempo_limite_s: float = 20.0) -> None:
        partes = urlsplit(base.rstrip("/"))
        if partes.scheme not in ("http", "https") or not partes.hostname:
            raise MotorErro(f"endereço inválido: {base!r}")
        self.seguro = partes.scheme == "https"
        self.host = partes.hostname
        self.porta = partes.port
        self.prefixo = partes.path
        self.tempo_limite_s = tempo_limite_s
        self._conn: http.client.HTTPConnection | None = None
        self._trava = threading.Lock()
        self._abortado = threading.Event()  # cortado de propósito: não é para tentar de novo

    def _conexao(self) -> http.client.HTTPConnection:
        if self._conn is None:
            classe = http.client.HTTPSConnection if self.seguro else http.client.HTTPConnection
            self._conn = classe(self.host, self.porta, timeout=self.tempo_limite_s)
        return self._conn

    def _fechar(self) -> None:
        conn, self._conn = self._conn, None
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()

    async def aquecer(self) -> None:
        """Abre a conexão (DNS e TLS) antes do primeiro pedido."""

        def abrir() -> None:
            with self._trava:
                self._conexao().connect()

        try:
            await asyncio.to_thread(abrir)
        except Exception as erro:
            self._fechar()
            log.warning("via rápida: não aqueceu a conexão (%s)", type(erro).__name__)

    async def linhas(
        self, caminho: str, corpo: dict[str, Any], cabecalhos: dict[str, str]
    ) -> AsyncIterator[str]:
        laco = asyncio.get_running_loop()
        fila: asyncio.Queue[object] = asyncio.Queue()
        parar = threading.Event()
        dados = json.dumps(corpo).encode()
        cab = {**cabecalhos, "Content-Type": "application/json", "Accept": "text/event-stream"}

        def por(item: object) -> None:
            laco.call_soon_threadsafe(fila.put_nowait, item)

        self._abortado.clear()

        def trabalhar() -> None:
            with self._trava:
                for tentativa in (1, 2):
                    recebeu = False
                    try:
                        conn = self._conexao()
                        conn.request("POST", self.prefixo + caminho, body=dados, headers=cab)
                        resp = conn.getresponse()
                        if resp.status != 200:
                            detalhe = resp.read(400).decode("utf-8", "replace")
                            self._fechar()
                            por(MotorErro(f"HTTP {resp.status}: {detalhe[:200]}"))
                            return
                        while not parar.is_set():
                            linha = resp.readline()
                            if not linha:
                                break
                            recebeu = True
                            por(linha.decode("utf-8", "replace").rstrip("\r\n"))
                        if parar.is_set():
                            self._fechar()  # resposta pela metade: a conexão não serve mais
                        por(_FIM)
                        return
                    except (http.client.RemoteDisconnected, ConnectionError) as erro:
                        # A conexão parada foi fechada do outro lado: refaz uma vez (nunca a
                        # que foi cortada daqui, por `abortar`).
                        self._fechar()
                        if recebeu or tentativa == 2 or self._abortado.is_set():
                            por(MotorErro(type(erro).__name__))
                            return
                    except Exception as erro:
                        self._fechar()
                        por(MotorErro(f"{type(erro).__name__}: {erro}"))
                        return

        threading.Thread(target=trabalhar, name="via-rapida", daemon=True).start()
        try:
            while True:
                item = await fila.get()
                if item is _FIM:
                    return
                if isinstance(item, Exception):
                    raise item
                yield str(item)
        finally:
            parar.set()

    def fechar(self) -> None:
        with self._trava:
            self._fechar()

    def abortar(self) -> None:
        """Corta o pedido em curso, de fora da thread que lê: o servidor vê a conexão cair e
        para de trabalhar nele (sem isto, um modelo local seguia lendo um prompt de minutos
        depois de o pedido ser abandonado, caso de 04/11/2026)."""
        self._abortado.set()
        sock = getattr(self._conn, "sock", None)
        if sock is not None:
            with contextlib.suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)


def _dados_sse(linhas: AsyncIterator[str]) -> AsyncIterator[dict[str, Any]]:
    async def gerar() -> AsyncIterator[dict[str, Any]]:
        async for linha in linhas:
            if not linha.startswith("data:"):
                continue
            conteudo = linha[5:].strip()
            if not conteudo or conteudo == "[DONE]":
                continue
            try:
                dados = json.loads(conteudo)
            except ValueError:
                continue
            if isinstance(dados, dict):
                yield dados

    return gerar()


def _raciocina(modelo: str) -> bool:
    """GPT-5 e a série "o" raciocinam; os outros recusam o parâmetro (aprendido no Ligatia)."""
    nome = modelo.rsplit("/", 1)[-1]
    return nome.startswith(("gpt-5", "o1", "o3", "o4"))


class MotorOpenAI:
    """chat/completions em fluxo: OpenAI, OpenRouter ou qualquer ponte compatível."""

    com_estado = False

    def __init__(
        self,
        nome: str,
        endereco: str,
        chave: str | None,
        modelo: str,
        raciocinio: str = "low",
        max_tokens: int = 300,
    ) -> None:
        self.nome = nome
        self.modelo = modelo
        self.chave = chave
        self.raciocinio = raciocinio
        self.max_tokens = max_tokens
        self.http = Http(endereco)
        self.uso: dict[str, Any] | None = None

    async def iniciar(self, sistema: str) -> None:
        await self.http.aquecer()

    def corpo(self, sistema: str, mensagens: list[dict[str, str]]) -> dict[str, Any]:
        corpo: dict[str, Any] = {
            "model": self.modelo,
            "stream": True,
            "messages": [{"role": "system", "content": sistema}, *mensagens],
        }
        if self.http.host == "api.openai.com":
            corpo["max_completion_tokens"] = self.max_tokens
        else:
            corpo["max_tokens"] = self.max_tokens
        if self.http.host in ("api.openai.com", "openrouter.ai"):
            # O último pedaço traz o uso (outras pontes podem recusar a opção).
            corpo["stream_options"] = {"include_usage": True}
        if self.raciocinio and _raciocina(self.modelo):
            if self.http.host == "openrouter.ai":
                corpo["reasoning"] = {"effort": self.raciocinio}
            else:
                corpo["reasoning_effort"] = self.raciocinio
        return corpo

    async def gerar(self, sistema: str, mensagens: list[dict[str, str]]) -> AsyncIterator[str]:
        cab = {"Authorization": f"Bearer {self.chave}"} if self.chave else {}
        linhas = self.http.linhas("/chat/completions", self.corpo(sistema, mensagens), cab)
        self.uso = None
        async for dados in _dados_sse(linhas):
            if erro := dados.get("error"):
                raise MotorErro(str(erro)[:200])
            if uso := dados.get("usage"):
                cache = int((uso.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
                self.uso = {
                    "input_tokens": max(0, int(uso.get("prompt_tokens") or 0) - cache),
                    "cache_read_input_tokens": cache,
                    "output_tokens": int(uso.get("completion_tokens") or 0),
                }
            for escolha in dados.get("choices") or []:
                if texto := (escolha.get("delta") or {}).get("content"):
                    yield texto

    async def interromper(self) -> None:
        return None

    async def reiniciar(self) -> None:
        return None

    async def fechar(self) -> None:
        self.http.fechar()


class MotorAnthropic:
    """Messages em fluxo, pela chave de API da Anthropic."""

    com_estado = False
    nome = "anthropic"

    def __init__(
        self, chave: str, modelo: str, endereco: str = ENDERECOS["anthropic"], max_tokens: int = 300
    ) -> None:
        self.modelo = modelo
        self.chave = chave
        self.max_tokens = max_tokens
        self.http = Http(endereco)
        self.uso: dict[str, Any] | None = None

    async def iniciar(self, sistema: str) -> None:
        await self.http.aquecer()

    async def gerar(self, sistema: str, mensagens: list[dict[str, str]]) -> AsyncIterator[str]:
        corpo = {
            "model": self.modelo,
            "max_tokens": self.max_tokens,
            "system": sistema,
            "messages": mensagens,
            "stream": True,
        }
        cab = {"x-api-key": self.chave, "anthropic-version": "2023-06-01"}
        self.uso = None
        async for dados in _dados_sse(self.http.linhas("/messages", corpo, cab)):
            tipo = dados.get("type")
            if tipo == "error":
                raise MotorErro(str(dados.get("error"))[:200])
            if tipo == "message_start":  # a entrada no começo; a saída cresce até o fim
                self.uso = dict((dados.get("message") or {}).get("usage") or {})
            elif tipo == "message_delta" and self.uso is not None:
                saida = (dados.get("usage") or {}).get("output_tokens")
                self.uso["output_tokens"] = saida or self.uso.get("output_tokens", 0)
            delta = dados.get("delta") or {}
            texto = delta.get("text") if delta.get("type") == "text_delta" else None
            if tipo == "content_block_delta" and texto:
                yield texto

    async def interromper(self) -> None:
        return None

    async def reiniciar(self) -> None:
        return None

    async def fechar(self) -> None:
        self.http.fechar()


class MotorPlano:
    """O Claude pela assinatura (SDK), com a persona enxuta e nenhuma ferramenta."""

    com_estado = True
    nome = "plano"

    def __init__(
        self,
        modelo: str,
        pasta: Path,
        foto: Callable[[], str] | None = None,
        conta: contas.Conta | None = None,
    ) -> None:
        self._modelo = modelo
        conta = conta or contas.Contas().em_uso("claude")
        self.cerebro = ClaudeBrain(
            modelo,
            [],
            pasta,
            tempo_limite_s=15.0,
            foto=foto,
            env={"CLAUDE_CONFIG_DIR": str(conta.onde), **pela_assinatura(conta)},
        )

    @property
    def uso(self) -> dict[str, Any] | None:
        return self.cerebro.uso

    @property
    def modelo(self) -> str:
        return self.cerebro.modelo_usado or self._modelo

    async def iniciar(self, sistema: str) -> None:
        await self.cerebro.start(sistema)

    async def gerar(self, sistema: str, mensagens: list[dict[str, str]]) -> AsyncIterator[str]:
        async for evento in self.cerebro.ask(mensagens[-1]["content"]):
            if isinstance(evento, Texto):
                yield evento.texto
            elif evento.erro:
                raise MotorErro(evento.erro)

    async def interromper(self) -> None:
        await self.cerebro.interrupt()

    async def reiniciar(self) -> None:
        await self.cerebro.reset()

    async def fechar(self) -> None:
        await self.cerebro.close()


def pela_assinatura(conta: contas.Conta) -> dict[str, str]:
    """O motor "plano" é a assinatura: com o login do Claude feito, a chave de API do painel não
    entra (ela tem a vez sobre o login e, sem crédito, derrubava toda resposta rápida no Live:
    teste de 27/10/2026)."""
    tem_login = conta.login.is_file() or bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))
    return {"ANTHROPIC_API_KEY": ""} if tem_login else {}


class MotorCodex(MotorPlano):
    """O Codex oficial pela conta que já está cadastrada, sem chave adicional."""

    nome = "codex"

    def __init__(
        self,
        modelo: str,
        pasta: Path,
        foto: Callable[[], str] | None = None,
        conta: contas.Conta | None = None,
    ) -> None:
        self._modelo = modelo
        self.cerebro = CodexBrain(modelo, [], pasta, tempo_limite_s=20.0, foto=foto, conta=conta)


class MotorContas:
    """Contas cadastradas com alternativa antes da primeira palavra; conserva a conversa."""

    nome = "contas"
    com_estado = True

    def __init__(self, motores: list[Motor]) -> None:
        self.motores = motores
        self.posicao = 0
        self.sistema = ""
        self.turnos: list[tuple[str, str]] = []

    @property
    def modelo(self) -> str:
        return self.motores[self.posicao].modelo

    @property
    def uso(self) -> dict[str, Any] | None:
        return self.motores[self.posicao].uso

    async def iniciar(self, sistema: str) -> None:
        self.sistema = sistema
        await self.motores[self.posicao].iniciar(sistema)

    async def gerar(self, sistema: str, mensagens: list[dict[str, str]]) -> AsyncIterator[str]:
        pedido = mensagens[-1]["content"]
        texto = pedido
        while True:
            resposta = ""
            motor = self.motores[self.posicao]
            try:
                async for pedaco in motor.gerar(sistema, [{"role": "user", "content": texto}]):
                    resposta += pedaco
                    yield pedaco
                self.turnos = [*self.turnos, (pedido, resposta)][-6:]
                return
            except MotorErro:
                if resposta.strip() or self.posicao + 1 == len(self.motores):
                    raise
                await motor.fechar()
                self.posicao += 1
                await self.motores[self.posicao].iniciar(self.sistema)
                contexto = "\n".join(f"Usuário: {p}\nZérvis: {r}" for p, r in self.turnos)
                texto = (
                    f"Conversa anterior (contexto):\n{contexto}\n\nPedido atual:\n"
                    if contexto
                    else ""
                ) + pedido
                log.info("voz rápida: alternativa da conta (%s)", self.motores[self.posicao].nome)

    async def interromper(self) -> None:
        await self.motores[self.posicao].interromper()

    async def reiniciar(self) -> None:
        await self.fechar()
        self.posicao, self.turnos = 0, []
        await self.iniciar(self.sistema)

    async def fechar(self) -> None:
        for motor in self.motores:
            with contextlib.suppress(Exception):
                await motor.fechar()
