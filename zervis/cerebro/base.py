"""Interface única do cérebro e a ponte que o roda num laço asyncio próprio.

O núcleo é síncrono (threads); o cérebro é assíncrono. A `Ponte` roda o cérebro numa thread
com seu próprio laço e conversa com o núcleo só por chamadas que não bloqueiam e por um
callback de eventos — assim o laço do microfone nunca espera rede (docs/06-qualidade.md).
"""

import asyncio
import logging
import re
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger(__name__)
FIM_DE_FRASE = re.compile(r"(?<=[.!?…])\s+")


@dataclass(frozen=True)
class Texto:
    """Pedaço de texto da resposta, na ordem em que chega."""

    texto: str


@dataclass(frozen=True)
class Fim:
    erro: str | None = None


EventoCerebro = Texto | Fim


@dataclass(frozen=True)
class Resposta:
    """A decisão falada do usuário e o que ele disse, para o cérebro ajustar o pedido."""

    aprovado: bool
    fala: str = ""

    def __bool__(self) -> bool:
        return self.aprovado


Aprovar = Callable[[str], Awaitable[Resposta]]
# Quem decide o prazo é a máquina de voz: 40 s depois de a pergunta terminar de tocar. Isto é só a
# rede de segurança; com 60 s, uma pergunta que demorou a tocar pelo celular expirava antes de a
# pessoa poder responder, e o "sim" atrasado travava o Zé (14/10/2026).
PRAZO_APROVACAO_S = 300.0


class Brain(Protocol):
    async def start(self, persona: str, aprovar: Aprovar | None = None) -> None: ...
    def ask(self, texto: str) -> AsyncIterator[EventoCerebro]: ...
    async def interrupt(self) -> None: ...
    async def reset(self) -> None: ...
    async def close(self) -> None: ...


class Frases:
    """Junta pedaços de texto e devolve frases completas, para falar por frase."""

    def __init__(self) -> None:
        self.resto = ""

    def somar(self, texto: str) -> list[str]:
        partes = FIM_DE_FRASE.split(self.resto + texto)
        self.resto = partes.pop()
        return [p.strip() for p in partes if p.strip()]

    def fechar(self) -> list[str]:
        resto, self.resto = self.resto.strip(), ""
        return [resto] if resto else []


class Ponte:
    """Leva pedidos ao cérebro e devolve frases e o fim por callbacks, fora da thread do núcleo."""

    def __init__(
        self,
        cerebro: Brain,
        persona: str,
        ao_falar: Callable[[int, str], None],
        ao_terminar: Callable[[int, str | None], None],
        ao_pedir_aprovacao: Callable[[int, str], None] | None = None,
        ao_primeiro_texto: Callable[[int, float], None] | None = None,
    ) -> None:
        self.cerebro = cerebro
        self.persona = persona
        self.ao_falar = ao_falar
        self.ao_terminar = ao_terminar
        self.ao_pedir_aprovacao = ao_pedir_aprovacao
        self.ao_primeiro_texto = ao_primeiro_texto
        self.laco = asyncio.new_event_loop()
        self.tarefa: asyncio.Task[None] | None = None
        self.marca = 0
        self.aprovacao: asyncio.Future[Resposta] | None = None
        self.ao_expirar_aprovacao: Callable[[], None] | None = None  # avisa a máquina de voz
        self.troca: asyncio.Lock | None = None  # criado no laço do cérebro
        threading.Thread(target=self.laco.run_forever, name="cerebro", daemon=True).start()
        asyncio.run_coroutine_threadsafe(
            self.cerebro.start(persona, self._aprovar), self.laco
        ).result(timeout=60)

    async def _aprovar(self, descricao: str) -> Resposta:
        """Chamado pelo cérebro (na thread dele): pergunta ao núcleo e espera o sim ou o não."""
        if self.ao_pedir_aprovacao is None:
            return Resposta(False)
        self.aprovacao = self.laco.create_future()
        self.ao_pedir_aprovacao(self.marca, descricao)
        try:
            return await asyncio.wait_for(self.aprovacao, PRAZO_APROVACAO_S)
        except TimeoutError:
            if self.ao_expirar_aprovacao is not None:
                self.ao_expirar_aprovacao()  # a máquina sai da confirmação, não fica presa
            return Resposta(False)
        finally:
            self.aprovacao = None

    @property
    def aprovacao_pendente(self) -> bool:
        return self.aprovacao is not None and not self.aprovacao.done()

    def responder_aprovacao(self, aprovado: bool, fala: str = "") -> None:
        def _responder() -> None:
            if self.aprovacao is not None and not self.aprovacao.done():
                self.aprovacao.set_result(Resposta(aprovado, fala))

        self.laco.call_soon_threadsafe(_responder)

    def perguntar(self, texto: str, marca: int) -> Future[None]:
        """`marca` volta nos callbacks: o núcleo descarta o que for de um pedido já abandonado."""
        return asyncio.run_coroutine_threadsafe(self._perguntar(texto, marca), self.laco)

    async def _perguntar(self, texto: str, marca: int) -> None:
        if self.tarefa and not self.tarefa.done():
            self.tarefa.cancel()
        self.tarefa = asyncio.current_task()
        self.marca = marca
        frases = Frases()
        primeiro = True
        erro: str | None = None
        try:
            async with self._troca():  # pedido durante uma troca espera o cérebro novo
                pass
            async for evento in self.cerebro.ask(texto):
                if isinstance(evento, Texto):
                    if primeiro and evento.texto.strip():
                        primeiro = False
                        if self.ao_primeiro_texto:
                            try:
                                self.ao_primeiro_texto(marca, time.monotonic())
                            except Exception as falha:
                                log.warning(
                                    "observador do cérebro falhou: %s", type(falha).__name__
                                )
                    for frase in frases.somar(evento.texto):
                        self.ao_falar(marca, frase)
                else:
                    erro = evento.erro
            for frase in frases.fechar():
                self.ao_falar(marca, frase)
        except asyncio.CancelledError:
            return  # interrompido: o núcleo já seguiu adiante, nada a avisar
        except Exception as e:
            log.exception("falha no cérebro")
            erro = type(e).__name__
        self.ao_terminar(marca, erro)

    def _troca(self) -> asyncio.Lock:
        if self.troca is None:
            self.troca = asyncio.Lock()
        return self.troca

    def trocar(self, novo: Brain) -> Future[None]:
        """Troca o cérebro: o pedido em curso é abandonado e o antigo é fechado."""

        async def _trocar() -> None:
            async with self._troca():
                await self._abandonar()
                antigo = self.cerebro
                await novo.start(self.persona, self._aprovar)
                self.cerebro = novo
                try:
                    await antigo.close()
                except Exception:
                    log.exception("falha ao fechar o cérebro antigo")

        return asyncio.run_coroutine_threadsafe(_trocar(), self.laco)

    async def _abandonar(self) -> None:
        if self.aprovacao is not None and not self.aprovacao.done():
            self.aprovacao.set_result(Resposta(False))  # interrompido no meio da pergunta: nega
        if self.tarefa and not self.tarefa.done():
            self.tarefa.cancel()

    def reiniciar(self) -> Future[None]:
        """Nova conversa: o cérebro esquece a sessão atual."""
        return asyncio.run_coroutine_threadsafe(self.cerebro.reset(), self.laco)

    def interromper(self) -> None:
        async def _interromper() -> None:
            await self._abandonar()
            await self.cerebro.interrupt()

        asyncio.run_coroutine_threadsafe(_interromper(), self.laco)

    def fechar(self) -> None:
        self.interromper()
        asyncio.run_coroutine_threadsafe(self.cerebro.close(), self.laco).result(timeout=10)
        self.laco.call_soon_threadsafe(self.laco.stop)
