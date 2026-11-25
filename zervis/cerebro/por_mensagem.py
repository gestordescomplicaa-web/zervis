"""Pedidos escritos fora do painel, num cérebro próprio: a conversa com o Zé pelo WhatsApp
(ADR 0102).

O chat do Início passa pela máquina de voz, que recusa pedidos com o Zé inativo (tela bloqueada,
você fora). Pelo WhatsApp você está justamente fora, então estes pedidos têm o próprio cérebro:
o mesmo provedor, a mesma persona e as mesmas ferramentas, numa sessão separada, sem voz.

- **Um pedido por vez**, na ordem em que chegam: um pedido nunca corta o anterior.
- **Sem confirmação pelo WhatsApp:** o que pede aprovação é negado, com o motivo para o modelo
  dizer que precisa da voz ou do painel. Quem tem o celular na mão não executa nada com efeito.
- **Sob demanda:** o cérebro sobe no primeiro pedido e fecha depois de `OCIOSO_S` parado; a
  sessão seguinte começa sem o histórico da anterior.
"""

import asyncio
import logging
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Any

from zervis.cerebro.base import Brain, Espera, Resposta, Texto

log = logging.getLogger(__name__)

OCIOSO_S = 30 * 60.0
FILA_MAXIMA = 10  # um laço ou uma enxurrada não vira uma fila de pedidos ao modelo
SEM_CONFIRMACAO = (
    "Pedido pelo WhatsApp: ações com efeito só com a confirmação pela voz ou pelo painel do Zé."
)
NOTA_DA_PERSONA = """\
## Conversa pelo WhatsApp

Os pedidos desta conversa chegam pelo WhatsApp, do número de quem usa para o número do Zé, \
escritos ou em áudio transcrito, não pela voz. Responda em texto curto, para ler no celular, sem \
tabelas nem títulos. É a mesma conversa da voz e do painel: o que foi dito por lá vem antes do \
pedido, entre <conversa> e </conversa>, só como contexto. Ações que pedem confirmação esperam a \
aprovação de quem usa no painel do Zé (o aviso sai sozinho); quando uma for negada, diga em uma \
frase que não foi aprovada no painel, sem tentar de novo."""
INICIO_DO_CONTEXTO = "<conversa>"
FIM_DO_CONTEXTO = "</conversa>"
MEMORIA = "mcp__jarvis__memoria"


@dataclass(frozen=True)
class Feito:
    """Um pedido respondido: o texto da resposta (vazio na falha), o erro do cérebro e para onde
    a resposta vai (o `destino` dado em `pedir`)."""

    pedido: str
    resposta: str
    erro: str | None
    destino: str = ""
    uso: dict[str, Any] | None = None


class ConversaPorMensagem:
    def __init__(
        self,
        criar: Callable[[], Brain],
        persona: Callable[[], str],
        ao_responder: Callable[[Feito], None],
        ocioso_s: float = OCIOSO_S,
        aprovar: Callable[[str, str], Awaitable[bool]] | None = None,
        contexto: Callable[[bool], str] | None = None,
    ) -> None:
        """`aprovar(descricao, destino)` espera a decisão de quem usa fora do WhatsApp;
        `contexto(novo)` dá o que foi dito por outros canais (`novo`: o cérebro acabou de subir)."""
        self.criar = criar
        self.persona = persona
        self.ao_responder = ao_responder
        self.ocioso_s = ocioso_s
        self.aprovar = aprovar
        self.contexto = contexto
        self._destino = ""  # para onde vai a resposta do pedido em curso
        self._laco: asyncio.AbstractEventLoop | None = None
        self._fila: asyncio.Queue[tuple[str, str] | None] | None = None
        self._pronto = threading.Event()
        self._trava = threading.Lock()
        self._fio: threading.Thread | None = None

    def pedir(self, texto: str, destino: str = "") -> bool:
        """Enfileira um pedido; False se a fila está cheia (o pedido não entra)."""
        self._garantir()
        laco, fila = self._laco, self._fila
        if laco is None or fila is None:
            return False
        aceito = threading.Event()

        def _enfileirar() -> None:
            if fila.qsize() < FILA_MAXIMA:
                fila.put_nowait((texto, destino))
                aceito.set()

        laco.call_soon_threadsafe(_enfileirar)
        return aceito.wait(5.0)

    def _garantir(self) -> None:
        with self._trava:
            if self._fio is not None and self._fio.is_alive():
                return
            self._pronto.clear()
            self._fio = threading.Thread(
                target=lambda: asyncio.run(self._principal()), name="conversa-whatsapp", daemon=True
            )
            self._fio.start()
        self._pronto.wait(5.0)

    async def _principal(self) -> None:
        self._laco = asyncio.get_running_loop()
        self._fila = asyncio.Queue()
        self._pronto.set()
        cerebro: Brain | None = None
        try:
            while True:
                try:
                    item = await asyncio.wait_for(self._fila.get(), self.ocioso_s)
                except TimeoutError:
                    if cerebro is not None:
                        log.info("conversa pelo WhatsApp: cérebro parado, fechado")
                        await _fechar(cerebro)
                        cerebro = None
                    continue
                if item is None:  # fechar()
                    return
                texto, destino = item
                novo = cerebro is None
                if cerebro is None:
                    try:
                        cerebro = await self._subir()
                    except Exception as falha:
                        log.exception("conversa pelo WhatsApp: o cérebro não subiu")
                        await self._entregar(Feito(texto, "", type(falha).__name__, destino))
                        continue
                self._destino = destino
                pedido = await self._com_contexto(texto, novo)
                feito = await _responder(cerebro, pedido, destino)
                await self._entregar(replace(feito, pedido=texto))
        finally:
            if cerebro is not None:
                await _fechar(cerebro)

    async def _subir(self) -> Brain:
        cerebro = self.criar()
        liberar_anotacoes(cerebro)
        await cerebro.start(f"{self.persona()}\n\n{NOTA_DA_PERSONA}", self._aprovar)
        return cerebro

    async def _aprovar(self, descricao: str) -> Resposta:
        if self.aprovar is None:
            return await _sem_confirmacao(descricao)
        try:
            aprovado = await self.aprovar(descricao, self._destino)
        except Exception:
            log.exception("conversa pelo WhatsApp: falha ao pedir a aprovação")
            aprovado = False
        return Resposta(aprovado)

    async def _com_contexto(self, texto: str, novo: bool) -> str:
        if self.contexto is None:
            return texto
        try:
            antes = await asyncio.to_thread(self.contexto, novo)
        except Exception:
            log.exception("conversa pelo WhatsApp: o contexto não veio")
            return texto
        if not antes:
            return texto
        return f"{INICIO_DO_CONTEXTO}\n{antes}\n{FIM_DO_CONTEXTO}\n\n{texto}"

    async def _entregar(self, feito: Feito) -> None:
        try:  # o envio bloqueia (rede): fora do laço do cérebro
            await asyncio.to_thread(self.ao_responder, feito)
        except Exception:
            log.exception("conversa pelo WhatsApp: a resposta não foi entregue")

    def fechar(self) -> None:
        laco, fila = self._laco, self._fila
        if laco is None or fila is None or laco.is_closed():
            return
        try:
            laco.call_soon_threadsafe(fila.put_nowait, None)
        except RuntimeError:
            return  # o laço já terminou
        if self._fio is not None:
            self._fio.join(timeout=10)


def liberar_anotacoes(cerebro: Brain) -> None:
    """Pelo WhatsApp, acrescentar à memória passa sem o "sim" (é anotar). Só a política de um
    turno normal muda: num turno de fora, a anotação continua pedindo a aprovação."""
    alvo: Any = cerebro
    if not hasattr(alvo, "autoaprovar"):
        return  # outro cérebro, sem a política de risco: tudo segue pedindo
    antes: Callable[[str, dict[str, Any]], bool] | None = alvo.autoaprovar

    def liberar(nome: str, entrada: dict[str, Any]) -> bool:
        if nome == MEMORIA and entrada.get("acao") == "adicionar":
            return True
        return antes is not None and antes(nome, entrada)

    alvo.autoaprovar = liberar


async def _sem_confirmacao(descricao: str) -> Resposta:
    log.info("conversa pelo WhatsApp: confirmação negada (%s)", descricao[:80])
    return Resposta(False, SEM_CONFIRMACAO)


async def _responder(cerebro: Brain, texto: str, destino: str) -> Feito:
    partes: list[str] = []
    erro: str | None = None
    try:
        async for evento in cerebro.ask(texto):
            if isinstance(evento, Espera):
                continue  # "Só um momento." é para a voz
            if isinstance(evento, Texto):
                partes.append(evento.texto)
            else:
                erro = evento.erro
    except Exception as falha:
        log.exception("conversa pelo WhatsApp: falha no cérebro")
        erro = type(falha).__name__
    return Feito(texto, "".join(partes).strip(), erro, destino, getattr(cerebro, "uso", None))


async def _fechar(cerebro: Brain) -> None:
    try:
        await cerebro.close()
    except Exception:
        log.exception("conversa pelo WhatsApp: falha ao fechar o cérebro")
