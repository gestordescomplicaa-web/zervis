"""Automações do Zé (Fase 7; modelo de job do Hermes, enxuto).

Quatro tipos:
- `lembrete`: na hora, o texto vira aviso falado. Zero modelo (ADR 0011: modo script).
- `ligacao`: na hora, o Zé liga para o número e dá o recado (ADR 0067); o texto é o JSON do
  pedido, aprovado pela voz quando foi agendado. O resultado vira aviso.
- `artigo`: na hora, o Zé pede um artigo do blog do site (ADR 0092), aprovado quando foi
  agendado; o texto é o JSON com o tema (vazio: a sessão escolhe pelo manual do site).
- `pergunta`: na hora, o cérebro responde o texto numa consulta separada, só com ferramentas de
  leitura, e a resposta vira aviso. Uma execução não cria outra automação (não recebe o
servidor
  MCP do Zé).

SQLite com transações entre processos sobrevive a reinícios; importa o `jobs.json` anterior.
`ultimo_status` é um conjunto fechado: quem
lê nunca conclui "o usuário recebeu" só porque é "ok" (o aviso pode estar esperando na fila).
Atrasado por o `jarvisd` estar parado: roda uma vez ao subir, sem repetir as perdidas.

A fila durável (plano de maturidade, Frente 1): cada vez que uma automação vence vira uma
execução no mesmo banco, na mesma transação que avança a agenda (pendente → rodando →
concluída, falhou ou interrompida, com as tentativas). Assim, um Zé morto no meio não perde a
execução nem a repete às cegas: ao subir, `retomar_ao_subir` decide pelo tipo (ADR 0069).
"""

import contextlib
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from zervis.automacoes.agenda import FUSO, interpretar
from zervis.dados.documentos import Documentos, lista_json

# ligacao: o Zé liga com um recado (ADR 0067); artigo: pede um artigo do blog (ADR 0092)
TIPOS = ("lembrete", "pergunta", "ligacao", "artigo")
STATUS = ("nunca", "ok", "erro", "bloqueado")
LIMITE_TEXTO = 600
ESTADOS = ("pendente", "rodando", "concluida", "falhou", "interrompida")
ABERTAS = ("pendente", "rodando")
# Uma pergunta interrompida roda de novo, até este total: só lê a internet, repetir é seguro.
TENTATIVAS = 2
GUARDADAS = 200  # execuções terminadas que ficam no histórico
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


@dataclass
class Execucao:
    """Uma vez em que a automação venceu, do disparo até o fim."""

    job: str
    nome: str
    tipo: str
    texto: str
    criada: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    estado: str = "pendente"
    tentativas: int = 0
    atualizada: str = ""
    erro: str = ""


def _agora_iso(agora: datetime) -> str:
    return agora.isoformat(timespec="seconds")


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

    # --- a fila durável das execuções ------------------------------------------------------

    def execucoes(self) -> list[Execucao]:
        with self._trava, self._dados.banco.transacao():
            return [Execucao(**dados) for dados in self._dados.listar("execucoes")]

    def _guardar_execucao(self, x: Execucao) -> None:
        self._dados.guardar("execucoes", asdict(x), x.id)

    def pendentes(self) -> list[Execucao]:
        return [x for x in self.execucoes() if x.estado == "pendente"]

    def disparar(self, agora: datetime) -> list[Execucao]:
        """As automações vencidas viram execuções pendentes, e a agenda delas avança, tudo numa
        transação: ou as duas coisas ficam gravadas, ou nenhuma. Uma automação com execução
        ainda aberta espera ela terminar (sem acumular)."""
        with self._trava, self._dados.banco.transacao():
            abertas = {x.job for x in self.execucoes() if x.estado in ABERTAS}
            novas = []
            for job in self.vencidos(agora):
                if job.id in abertas:
                    continue
                x = Execucao(
                    job.id, job.nome, job.tipo, job.texto, _agora_iso(agora),
                    atualizada=_agora_iso(agora),
                )  # fmt: skip
                self._guardar_execucao(x)
                seguinte = interpretar(job.agenda).seguinte(agora)
                self._mudar(
                    job.id,
                    proxima=seguinte.isoformat() if seguinte else "",
                    ativo=job.ativo and seguinte is not None,
                )
                novas.append(x)
            return novas

    def _execucao(self, id_: str) -> Execucao:
        dados = self._dados.ler("execucoes", id_)
        if dados is None:
            raise JobErro(f"execução {id_} não encontrada")
        return Execucao(**dados)

    def iniciar(self, id_: str, agora: datetime) -> Execucao:
        """Antes de rodar: uma tentativa a mais, gravada antes do efeito."""
        with self._trava, self._dados.banco.transacao():
            x = self._execucao(id_)
            x.estado, x.tentativas, x.atualizada = "rodando", x.tentativas + 1, _agora_iso(agora)
            self._guardar_execucao(x)
            return x

    def concluir(self, id_: str, status: str, agora: datetime, erro: str = "") -> Execucao:
        """Depois de rodar: o fim da execução e o último resultado da automação."""
        with self._trava, self._dados.banco.transacao():
            if status not in STATUS[1:]:
                raise JobErro(f"status desconhecido: {status}")
            x = self._execucao(id_)
            x.estado = "concluida" if status == "ok" else "falhou"
            x.erro, x.atualizada = erro[:200], _agora_iso(agora)
            self._guardar_execucao(x)
            with contextlib.suppress(JobErro):  # a automação pode ter sido removida
                self._mudar(
                    x.job, ultima=_agora_iso(agora), ultimo_status=status, ultimo_erro=erro[:200]
                )
            self._podar()
            return x

    def _podar(self) -> None:
        terminadas = [x for x in self.execucoes() if x.estado not in ABERTAS]
        for x in terminadas[: max(0, len(terminadas) - GUARDADAS)]:
            self._dados.remover("execucoes", x.id)

    def retomar_ao_subir(self, agora: datetime) -> list[Execucao]:
        """O que estava rodando quando o Zé caiu. O lembrete volta para a fila (repetir um
        lembrete é melhor que perdê-lo); a pergunta também, até `TENTATIVAS`; a ligação não:
        ela pode ter sido feita, e ligar duas vezes não se desfaz. Devolve as interrompidas,
        para o Zé avisar."""
        interrompidas = []
        with self._trava, self._dados.banco.transacao():
            for x in self.execucoes():
                if x.estado != "rodando":
                    continue
                x.atualizada = _agora_iso(agora)
                if x.tipo == "lembrete" or (x.tipo == "pergunta" and x.tentativas < TENTATIVAS):
                    x.estado = "pendente"
                else:
                    x.estado, x.erro = "interrompida", "o Zé reiniciou no meio"
                    interrompidas.append(x)
                self._guardar_execucao(x)
            for x in interrompidas:
                with contextlib.suppress(JobErro):
                    self._mudar(
                        x.job,
                        ultima=x.atualizada,
                        ultimo_status="erro",
                        ultimo_erro="interrompida por um reinício",
                    )
        return interrompidas
