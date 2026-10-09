"""Monitor da oficina: só o que o JARVIS delegou (roadmap, Fase 3).

Uma thread espera a caixa do Run (`check --wait`) e transforma cada mensagem num aviso falado:
- `worker_done`: "deu certo" ou "falhou" com o resumo do agente; o terminal é liberado (o Orca
  guarda a saída, que continua legível por `worker-read`);
- `question`: a pergunta do agente, guardada para o usuário responder por voz;
- `escalation`: o agente travou e pede ajuda.
Sessões conduzidas pelo teclado não entram aqui: elas não são deste Run.

O lote só é confirmado (`--ack`) depois de todos os avisos postos na fila; se o `jarvisd` cair no
meio, o Orca entrega o mesmo lote de novo.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from jarvis.oficina.oficina import AGENTES, Mensagem, Oficina
from jarvis.oficina.orca import OrcaErro

log = logging.getLogger(__name__)
ESPERA_MS = 60_000
PAUSA_ERRO_S = 15.0


@dataclass(frozen=True)
class Pergunta:
    id: str
    agente: str
    projeto: str
    texto: str


def _resumo(m: Mensagem) -> str:
    return str(m.dados.get("summary") or m.corpo or m.assunto).strip()


def aviso(m: Mensagem, tarefa: dict[str, str]) -> str:
    agente = AGENTES.get(tarefa.get("agente", ""), "agente")
    onde = f" no projeto {tarefa['projeto']}" if tarefa.get("projeto") else ""
    if m.tipo == "worker_done":
        deu_certo = str(m.dados.get("outcome", "")).lower() == "succeeded"
        estado = "deu certo" if deu_certo else "falhou"
        return f"O {agente} terminou{onde}: {estado}. {_resumo(m)}".strip()
    if m.tipo == "question":
        return f"O {agente}{onde} pergunta: {_resumo(m)}"
    return f"O {agente}{onde} precisa de ajuda: {_resumo(m)}"


def dispatch_de(m: Mensagem) -> str:
    return str(m.dados.get("dispatchId") or m.dados.get("dispatch_id") or "")


class Monitor:
    def __init__(self, oficina: Oficina, avisar: Callable[[str], None], parar: threading.Event):
        self.oficina = oficina
        self.avisar = avisar
        self.parar = parar
        self.perguntas: dict[str, Pergunta] = {}

    def start(self) -> None:
        threading.Thread(target=self._rodar, name="oficina", daemon=True).start()

    def tratar(self, mensagens: list[Mensagem]) -> None:
        for m in mensagens:
            dispatch = dispatch_de(m)
            tarefa = self.oficina.tarefas.get(dispatch, {})
            if m.tipo not in ("worker_done", "question", "escalation"):
                continue
            log.info("oficina: %s de %s", m.tipo, dispatch or "?")
            self.avisar(aviso(m, tarefa))
            if m.tipo == "question":
                agente = AGENTES.get(tarefa.get("agente", ""), "agente")
                self.perguntas[m.id] = Pergunta(m.id, agente, tarefa.get("projeto", ""), _resumo(m))
            elif m.tipo == "worker_done" and dispatch:
                self.oficina.concluir(dispatch)
                self.oficina.liberar(dispatch)

    def _rodar(self) -> None:
        while not self.parar.is_set():
            if self.oficina.run is None:
                self.parar.wait(5)  # nada delegado ainda: o Run nasce na primeira delegação
                continue
            try:
                entrega, mensagens = self.oficina.caixa(ESPERA_MS)
                if entrega is None:
                    continue
                self.tratar(mensagens)
                self.oficina.confirmar(entrega)
            except OrcaErro as erro:
                log.warning("oficina: caixa indisponível: %s", erro)
                self.parar.wait(PAUSA_ERRO_S)
            except Exception:
                log.exception("oficina: falha no monitor")
                self.parar.wait(PAUSA_ERRO_S)
