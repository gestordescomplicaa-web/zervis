"""Automações do Zé (Fase 7; modelo de job do Hermes, enxuto).

Dois tipos:
- `lembrete`: na hora, o texto vira aviso falado. Zero modelo (ADR 0011: modo script).
- `pergunta`: na hora, o cérebro responde o texto numa consulta separada, só com ferramentas de
  leitura, e a resposta vira aviso. Uma execução não cria outra automação (não recebe o
servidor
  MCP do Zé).

SQLite com transações entre processos sobrevive a reinícios; importa o `jobs.json` anterior.
`ultimo_status` é um conjunto fechado: quem
lê nunca conclui "o usuário recebeu" só porque é "ok" (o aviso pode estar esperando na fila).
Atrasado por o `jarvisd` estar parado: roda uma vez ao subir, sem repetir as perdidas.
"""

import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from zervis.automacoes.agenda import FUSO, interpretar
from zervis.dados.documentos import Documentos, lista_json

TIPOS = ("lembrete", "pergunta")
STATUS = ("nunca", "ok", "erro", "bloqueado")
LIMITE_TEXTO = 600
_TRAVAS: dict[Path, threading.RLock] = {}
_CRIAR_TRAVA = threading.Lock()


class JobErro(ValueError):
    pass


@dataclass
class Job:
    nome: str
    agenda: str
    tipo: str
    texto: str
    proxima: str  # ISO; "" quando não roda mais
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:6])
    ativo: bool = True
    criado: str = field(default_factory=lambda: datetime.now(FUSO).isoformat(timespec="seconds"))
    ultima: str = ""
    ultimo_status: str = "nunca"
    ultimo_erro: str = ""

    def resumo(self) -> str:
        quando = (
            datetime.fromisoformat(self.proxima).strftime("%d/%m %H:%M") if self.proxima else "-"
        )
        estado = "ativo" if self.ativo else "pausado"
        return f"{self.nome} ({self.tipo}, {self.agenda}; próxima {quando}; {estado})"


class Jobs:
    def __init__(self, arquivo: Path) -> None:
        self._dados = Documentos(arquivo)
        self.arquivo = self._dados.banco.arquivo
        self._dados.importar(arquivo, lista_json, "jobs", campo_chave="id")
        # Um processo é dono do estado, mas painel e agendador têm várias threads.
        # Instâncias que apontam ao mesmo arquivo também precisam da mesma transação.
        with _CRIAR_TRAVA:
            self._trava = _TRAVAS.setdefault(self.arquivo.resolve(), threading.RLock())

    def listar(self) -> list[Job]:
        with self._trava, self._dados.banco.transacao():
            return [Job(**dados) for dados in self._dados.listar("jobs")]

    def _gravar(self, jobs: list[Job]) -> None:
        self._dados.substituir("jobs", [asdict(j) for j in jobs], "id")

    def criar(self, nome: str, agenda: str, tipo: str, texto: str, agora: datetime) -> Job:
        with self._trava, self._dados.banco.transacao():
            if tipo not in TIPOS:
                raise JobErro(f"tipo deve ser {' ou '.join(TIPOS)}")
            texto = " ".join(texto.split())
            if not texto or len(texto) > LIMITE_TEXTO:
                raise JobErro("texto vazio ou longo demais")
            try:
                a = interpretar(agenda)
                primeira = a.primeira(agora)
            except ValueError as erro:
                raise JobErro(str(erro)) from None
            job = Job(
                " ".join(nome.split())[:60] or texto[:40],
                a.texto,
                tipo,
                texto,
                primeira.isoformat(),
            )
            self._gravar([*self.listar(), job])
            return job

    def _mudar(self, id_: str, **mudancas: object) -> Job:
        with self._trava, self._dados.banco.transacao():
            jobs = self.listar()
            for j in jobs:
                if j.id == id_:
                    for chave, valor in mudancas.items():
                        setattr(j, chave, valor)
                    self._gravar(jobs)
                    return j
            raise JobErro(f"automação {id_} não encontrada")

    def pausar(self, id_: str) -> Job:
        return self._mudar(id_, ativo=False)

    def retomar(self, id_: str, agora: datetime) -> Job:
        with self._trava, self._dados.banco.transacao():
            job = next((j for j in self.listar() if j.id == id_), None)
            if job is None:
                raise JobErro(f"automação {id_} não encontrada")
            a = interpretar(job.agenda)
            proxima = job.proxima
            if not proxima or datetime.fromisoformat(proxima) <= agora:
                proxima = a.primeira(agora).isoformat() if a.repete else ""
            return self._mudar(id_, ativo=True, proxima=proxima)

    def remover(self, id_: str) -> Job:
        with self._trava, self._dados.banco.transacao():
            jobs = self.listar()
            achado = next((j for j in jobs if j.id == id_), None)
            if achado is None:
                raise JobErro(f"automação {id_} não encontrada")
            self._gravar([j for j in jobs if j.id != id_])
            return achado

    def vencidos(self, agora: datetime) -> list[Job]:
        return [
            j
            for j in self.listar()
            if j.ativo and j.proxima and datetime.fromisoformat(j.proxima) <= agora
        ]

    def registrar(self, id_: str, status: str, agora: datetime, erro: str = "") -> Job:
        """Depois de rodar: status fechado e a próxima vez (a partir de agora, sem repor)."""
        with self._trava, self._dados.banco.transacao():
            if status not in STATUS:
                raise JobErro(f"status desconhecido: {status}")
            job = next((j for j in self.listar() if j.id == id_), None)
            if job is None:
                raise JobErro(f"automação {id_} não encontrada")
            seguinte = interpretar(job.agenda).seguinte(agora)
            return self._mudar(
                id_,
                ultima=agora.isoformat(timespec="seconds"),
                ultimo_status=status,
                ultimo_erro=erro[:200],
                proxima=seguinte.isoformat() if seguinte else "",
                ativo=job.ativo and seguinte is not None,
            )
