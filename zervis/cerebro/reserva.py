"""Alternativas de conta/provedor antes de qualquer resposta ou ferramenta: sem repetir ações."""

import contextlib
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from zervis.cerebro.base import Aprovar, Brain, EventoCerebro, Fim, Texto

log = logging.getLogger(__name__)
RECUPERAVEIS = {
    "limite_de_uso",
    "acesso_invalido",
    "tempo_esgotado",
    "falha_codex",
    "falha_claude",
    "sem_resposta",
    "transporte_encerrado",
}


class ComReserva:
    def __init__(self, cerebro: Brain, alternativas: list[tuple[str, Callable[[], Brain]]]) -> None:
        self.cerebro_ativo = cerebro
        self.principal = cerebro
        self.alternativas = alternativas
        self.proxima = 0
        self.persona = ""
        self.aprovar: Aprovar | None = None
        self.turnos: list[tuple[str, str]] = []
        self.uso: dict[str, Any] | None = None
        self.ferramentas_usadas: list[str] = []

    @property
    def modelo(self) -> str:
        return str(getattr(self.cerebro_ativo, "modelo", ""))

    @property
    def modelo_usado(self) -> str | None:
        return getattr(self.cerebro_ativo, "modelo_usado", None)

    @property
    def limite(self) -> dict[str, Any]:
        return dict(getattr(self.cerebro_ativo, "limite", {}))

    async def start(self, persona: str, aprovar: Aprovar | None = None) -> None:
        self.persona, self.aprovar = persona, aprovar
        await self.cerebro_ativo.start(persona, aprovar)

    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        self.uso, self.ferramentas_usadas = None, []
        pedido = texto
        while True:
            resposta = ""
            erro: str | None = None
            try:
                async for evento in self.cerebro_ativo.ask(pedido):
                    if isinstance(evento, Texto):
                        resposta += evento.texto
                        yield evento
                    else:
                        erro = evento.erro
            except (OSError, TimeoutError):
                erro = "tempo_esgotado"
            self.ferramentas_usadas = list(getattr(self.cerebro_ativo, "ferramentas_usadas", []))
            if uso := getattr(self.cerebro_ativo, "uso", None):
                soma: dict[str, Any] = self.uso or {}
                self.uso = {
                    k: int(soma.get(k) or 0) + int(uso.get(k) or 0)
                    for k in (
                        "input_tokens",
                        "cache_read_input_tokens",
                        "cache_creation_input_tokens",
                        "output_tokens",
                    )
                }
            if not erro:
                self.turnos = [*self.turnos, (texto, resposta)][-6:]
                yield Fim()
                return
            if (
                erro not in RECUPERAVEIS
                or resposta.strip()
                or self.ferramentas_usadas
                or self.proxima == len(self.alternativas)
            ):
                yield Fim(erro)
                return
            if not await self._alternar():
                yield Fim(erro)
                return
            contexto = "\n".join(f"Usuário: {p}\nZérvis: {r}" for p, r in self.turnos)
            pedido = (
                f"Conversa anterior (contexto):\n{contexto}\n\nPedido atual:\n" if contexto else ""
            ) + texto

    async def _alternar(self) -> bool:
        while self.proxima < len(self.alternativas):
            nome, criar = self.alternativas[self.proxima]
            self.proxima += 1
            novo: Brain | None = None
            try:
                novo = criar()
                await novo.start(self.persona, self.aprovar)
            except Exception as erro:
                log.warning("alternativa indisponível: %s (%s)", nome, type(erro).__name__)
                if novo is not None:
                    with contextlib.suppress(Exception):
                        await novo.close()
                continue
            with contextlib.suppress(Exception):
                await self.cerebro_ativo.close()
            self.cerebro_ativo = novo
            log.info("cérebro: alternativa %s", nome)
            return True
        return False

    async def interrupt(self) -> None:
        await self.cerebro_ativo.interrupt()

    async def reset(self) -> None:
        self.turnos = []
        self.proxima = 0
        if self.cerebro_ativo is not self.principal:
            await self.cerebro_ativo.close()
            self.cerebro_ativo = self.principal
        await self.cerebro_ativo.reset()

    async def close(self) -> None:
        await self.cerebro_ativo.close()
