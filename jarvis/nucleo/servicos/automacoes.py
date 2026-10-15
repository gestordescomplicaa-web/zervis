"""Serviço de automacoes; pode ser exercitado com dependências próprias, sem subir o núcleo."""

import asyncio
import logging
import queue
from datetime import datetime
from typing import Any, Protocol

from jarvis.automacoes import executor
from jarvis.automacoes.agenda import FUSO
from jarvis.automacoes.calendario import Calendario
from jarvis.automacoes.jobs import Job, Jobs
from jarvis.avisos.fila import PRIORIDADES, Fila
from jarvis.cerebro.base import Ponte
from jarvis.cerebro.claude import carimbo
from jarvis.cerebro.consumo import Consumo
from jarvis.config import Config
from jarvis.nucleo import estados as e
from jarvis.nucleo.apoio import DADOS
from jarvis.sistema.vigia import Eventos, Vigia

log = logging.getLogger(__name__)


class ContextoAutomacoes(Protocol):
    _agenda_em: Any
    _meta: dict[str, dict[str, Any]]
    _rodando: set[str]
    _vigia_em: Any
    calendario: Calendario
    cfg: Config
    consumo: Consumo
    eventos: queue.Queue[e.Evento]
    eventos_sistema: Eventos
    fila: Fila
    jobs: Jobs
    maquina: e.Maquina
    ponte: Ponte
    vigia: Vigia

    def _na_linha(self, tipo: str, texto: str) -> None: ...
    async def _rodar_pergunta(self, job: Job) -> None: ...


class ServicoAutomacoes:
    def __init__(self, contexto: ContextoAutomacoes) -> None:
        self.n = contexto

    def _agendador(self, agora: float) -> None:
        momento = datetime.fromtimestamp(agora, FUSO)
        for job in self.n.jobs.vencidos(momento):
            if job.id in self.n._rodando:
                continue
            if job.tipo == "lembrete":
                log.info("automação %s: lembrete", job.id)
                self.n._na_linha("lembrete", job.texto)
                self.n.jobs.registrar(job.id, "ok", momento)
                lembrete = f"Lembrete: {job.texto}"
                self.n._meta[lembrete] = {
                    "prioridade": PRIORIDADES["lembrete"],
                    "titulo": "um lembrete",
                }
                self.n.eventos.put(e.Aviso(lembrete))
            else:
                self.n._rodando.add(job.id)
                asyncio.run_coroutine_threadsafe(self.n._rodar_pergunta(job), self.n.ponte.laco)
        for texto in self.n.eventos_sistema.novos():
            log.info("evento do sistema: %s", texto)
            self.n.eventos.put(e.Aviso(texto))
        if agora - self.n._vigia_em >= 60:
            self.n._vigia_em = agora
            for texto in self.n.vigia.amostrar(agora):
                log.info("vigia: %s", texto)
                self.n.eventos.put(e.Aviso(texto))
        if agora - self.n._agenda_em >= 30:
            self.n._agenda_em = agora
            for texto, expira in self.n.calendario.vencidos(agora):
                log.info("agenda: %s", texto)
                if self.n.maquina.estado is e.Estado.ATIVO:
                    self.n.eventos.put(e.Aviso(texto))
                else:
                    self.n.fila.guardar(texto, "agenda", expira)  # some quando a reunião começa

    async def _rodar_pergunta(self, job: Job) -> None:
        momento = datetime.now(FUSO)
        try:
            texto, uso = await executor.executar(
                job.texto, self.n.cfg["cerebro"]["modelo"], DADOS / "cerebro", carimbo(momento)
            )
            self.n.consumo.somar(uso, "automação")
            self.n.jobs.registrar(job.id, "ok" if texto else "erro", momento)
            if texto:
                self.n.eventos.put(e.Aviso(texto))
        except Exception as erro:
            log.exception("automação %s falhou", job.id)
            self.n.jobs.registrar(job.id, "erro", momento, type(erro).__name__)
            self.n.eventos.put(e.Aviso(f"A automação {job.nome} falhou."))
        finally:
            self.n._rodando.discard(job.id)
