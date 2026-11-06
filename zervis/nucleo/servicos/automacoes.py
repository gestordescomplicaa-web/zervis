"""Serviço de automacoes; pode ser exercitado com dependências próprias, sem subir o núcleo."""

import asyncio
import json
import logging
import queue
import threading
from datetime import datetime
from typing import Any, Protocol

from zervis import atividade
from zervis.automacoes import executor
from zervis.automacoes.agenda import FUSO
from zervis.automacoes.calendario import Calendario
from zervis.automacoes.jobs import Execucao, Jobs
from zervis.avisos import modo as modo_fala
from zervis.avisos.fila import PRIORIDADES, Fila
from zervis.cerebro.base import Ponte
from zervis.cerebro.claude import carimbo
from zervis.cerebro.consumo import Consumo
from zervis.config import Config
from zervis.nucleo import estados as e
from zervis.nucleo.apoio import DADOS
from zervis.sistema.vigia import Eventos, Vigia
from zervis.sistema.vigia_n8n import VigiaN8n
from zervis.versoes import DIA_S, Versoes

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
    modo_fala: Any
    ponte: Ponte
    vigia: Vigia
    vigia_n8n: VigiaN8n
    _n8n_em: Any
    _n8n_conferindo: threading.Event
    versoes: Versoes
    _versoes_em: Any
    _versoes_procurando: threading.Event

    def _na_linha(self, tipo: str, texto: str) -> None: ...
    def fazer_ligacao(self, telefone: str, nome: str, recado: str) -> str: ...
    async def _rodar_pergunta(self, x: Execucao) -> None: ...


class ServicoAutomacoes:
    def __init__(self, contexto: ContextoAutomacoes) -> None:
        self.n = contexto

    def _agendador(self, agora: float) -> None:
        momento = datetime.fromtimestamp(agora, FUSO)
        # A fila durável (ADR 0069): vencer vira uma execução gravada; rodar vem depois.
        self.n.jobs.disparar(momento)
        for x in self.n.jobs.pendentes():
            if x.id not in self.n._rodando:
                self._executar(x, momento)
        for texto in self.n.eventos_sistema.novos():
            log.info("evento do sistema: %s", texto)
            self.n.eventos.put(e.Aviso(texto))
        if agora - self.n._vigia_em >= 60:
            self.n._vigia_em = agora
            for texto in self.n.vigia.amostrar(agora):
                log.info("vigia: %s", texto)
                self.n.eventos.put(e.Aviso(texto))
        if agora - self.n._n8n_em >= 60 and not self.n._n8n_conferindo.is_set():
            self.n._n8n_em = agora
            self.n._n8n_conferindo.set()
            # Pela rede, com tempo limite: numa thread, para nunca atrasar os lembretes.
            threading.Thread(target=self._vigiar_n8n, name="vigia-n8n", daemon=True).start()
        if agora - self.n._versoes_em >= DIA_S and not self.n._versoes_procurando.is_set():
            self.n._versoes_em = agora
            self.n._versoes_procurando.set()
            threading.Thread(target=self._procurar_versao, name="versoes", daemon=True).start()
        if agora - self.n._agenda_em >= 30:
            self.n._agenda_em = agora
            # A atualização pelo painel termina depois que este processo (o novo) subiu.
            if (atualizou := self.n.versoes.resultado_novo()) is not None:
                atividade.PADRAO.registrar("execucao", atualizou, origem="atualizacoes")
                self.n._na_linha("aviso", atualizou)
                if modo_fala.falar(modo_fala.efetivo(self.n), "notificacao"):
                    self.n.eventos.put(e.Aviso(atualizou))
            for texto, expira in self.n.calendario.vencidos(agora):
                log.info("agenda: %s", texto)
                if self.n.maquina.estado is e.Estado.ATIVO:
                    self.n.eventos.put(e.Aviso(texto))
                else:
                    self.n.fila.guardar(texto, "agenda", expira)  # some quando a reunião começa

    def _executar(self, x: Execucao, momento: datetime) -> None:
        """Marca a tentativa antes do efeito: se o Zé cair no meio, quem sobe sabe."""
        x = self.n.jobs.iniciar(x.id, momento)
        if x.tipo == "lembrete":
            log.info("automação %s: lembrete", x.job)
            self.n._na_linha("lembrete", x.texto)
            lembrete = f"Lembrete: {x.texto}"
            self.n._meta[lembrete] = {
                "prioridade": PRIORIDADES["lembrete"],
                "titulo": "um lembrete",
            }
            self.n.eventos.put(e.Aviso(lembrete))
            self.n.jobs.concluir(x.id, "ok", momento)
        elif x.tipo == "ligacao":
            log.info("automação %s: ligação agendada", x.job)
            self.n._rodando.add(x.id)
            threading.Thread(
                target=self._ligar_agendado, args=(x,), name="ligacao-agendada", daemon=True
            ).start()
        else:
            self.n._rodando.add(x.id)
            asyncio.run_coroutine_threadsafe(self.n._rodar_pergunta(x), self.n.ponte.laco)

    def retomar_execucoes(self) -> None:
        """Ao subir: o que o Zé deixou no meio volta para a fila ou vira aviso (ADR 0069)."""
        for x in self.n.jobs.retomar_ao_subir(datetime.now(FUSO)):
            if x.tipo == "ligacao":
                texto = (
                    f"A ligação agendada {x.nome} foi interrompida por um reinício e pode não "
                    "ter sido feita. Peça de novo se ainda quiser."
                )
            else:
                texto = f"A automação {x.nome} foi interrompida por um reinício."
            atividade.PADRAO.registrar(
                "falha", f"Automação interrompida: {x.nome}", origem="automacoes"
            )
            self.n._na_linha("aviso", texto)
            self.n.fila.guardar(texto, "automacao")

    def _ligar_agendado(self, x: Execucao) -> None:
        """A ligação agendada (ADR 0067): aprovada pela voz quando foi agendada; o resultado vem
        como aviso, como a de agora."""
        status, erro = "ok", ""
        try:
            pedido = json.loads(x.texto)
            self.n.fazer_ligacao(str(pedido["t"]), str(pedido.get("n", "")), str(pedido["r"]))
        except (ValueError, KeyError, TypeError):
            log.warning("ligação agendada com o pedido ilegível")
            status, erro = "erro", "pedido ilegível"
        except RuntimeError:
            status, erro = "erro", "não ligou"  # o aviso de que não ligou já saiu
        finally:
            self.n.jobs.concluir(x.id, status, datetime.now(FUSO), erro)
            self.n._rodando.discard(x.id)

    def _procurar_versao(self) -> None:
        """A procura diária de atualização (pela rede, numa thread): na tela e, se o modo de
        fala deixar, falada. Nunca instala."""
        try:
            if (texto := self.n.versoes.procurar_do_dia()) is not None:
                self.n._na_linha("aviso", texto)
                if modo_fala.falar(modo_fala.efetivo(self.n), "notificacao"):
                    self.n.eventos.put(e.Aviso(texto))
        except Exception:
            log.exception("procura de atualização falhou")
        finally:
            self.n._versoes_procurando.clear()

    def _vigiar_n8n(self) -> None:
        """Os n8n dos conectores (ADR 0038): "fora do ar" e "voltou", na tela, na Atividade e
        falado conforme o modo de fala."""
        try:
            for prioridade, texto in self.n.vigia_n8n.amostrar():
                log.info("vigia do n8n: %s", texto)
                atividade.PADRAO.registrar("execucao", texto, origem="vigia")
                self.n._na_linha("aviso", texto)
                if modo_fala.falar(modo_fala.efetivo(self.n), prioridade):
                    self.n._meta[texto] = {"prioridade": PRIORIDADES[prioridade], "titulo": "o n8n"}
                    self.n.eventos.put(e.Aviso(texto))
        except Exception:
            log.exception("vigia do n8n falhou")
        finally:
            self.n._n8n_conferindo.clear()

    async def _rodar_pergunta(self, x: Execucao) -> None:
        momento = datetime.now(FUSO)
        try:
            texto, uso = await executor.executar(
                x.texto, self.n.cfg["cerebro"]["modelo"], DADOS / "cerebro", carimbo(momento)
            )
            self.n.consumo.somar(uso, "automação")
            self.n.jobs.concluir(x.id, "ok" if texto else "erro", datetime.now(FUSO))
            if texto:
                self.n.eventos.put(e.Aviso(texto))
        except Exception as erro:
            log.exception("automação %s falhou", x.job)
            self.n.jobs.concluir(x.id, "erro", datetime.now(FUSO), type(erro).__name__)
            self.n.eventos.put(e.Aviso(f"A automação {x.nome} falhou."))
        finally:
            self.n._rodando.discard(x.id)
