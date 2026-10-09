"""Automações do JARVIS (Fase 7; modelo de job do Hermes, enxuto).

Dois tipos:
- `lembrete`: na hora, o texto vira aviso falado. Zero modelo (ADR 0011: modo script).
- `pergunta`: na hora, o cérebro responde o texto numa consulta separada, só com ferramentas de
  leitura, e a resposta vira aviso. Uma execução não cria outra automação (não recebe o servidor
  MCP do JARVIS).

`jobs.json` com escrita atômica sobrevive a reinícios. `ultimo_status` é um conjunto fechado: quem
lê nunca conclui "o usuário recebeu" só porque é "ok" (o aviso pode estar esperando na fila).
Atrasado por o `jarvisd` estar parado: roda uma vez ao subir, sem repetir as perdidas.
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from jarvis.automacoes.agenda import FUSO, interpretar

TIPOS = ("lembrete", "pergunta")
STATUS = ("nunca", "ok", "erro", "bloqueado")
LIMITE_TEXTO = 600


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
        self.arquivo = arquivo

    def listar(self) -> list[Job]:
        try:
            brutos = json.loads(self.arquivo.read_text())
        except (OSError, ValueError):
            return []
        return [Job(**j) for j in brutos if isinstance(j, dict)]

    def _gravar(self, jobs: list[Job]) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporario = self.arquivo.with_suffix(".next")
        temporario.write_text(json.dumps([asdict(j) for j in jobs], ensure_ascii=False, indent=1))
        temporario.chmod(0o600)
        temporario.replace(self.arquivo)

    def criar(self, nome: str, agenda: str, tipo: str, texto: str, agora: datetime) -> Job:
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
            " ".join(nome.split())[:60] or texto[:40], a.texto, tipo, texto, primeira.isoformat()
        )
        self._gravar([*self.listar(), job])
        return job

    def _mudar(self, id_: str, **mudancas: object) -> Job:
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
        job = next((j for j in self.listar() if j.id == id_), None)
        if job is None:
            raise JobErro(f"automação {id_} não encontrada")
        a = interpretar(job.agenda)
        proxima = job.proxima
        if not proxima or datetime.fromisoformat(proxima) <= agora:
            proxima = a.primeira(agora).isoformat() if a.repete else ""
        return self._mudar(id_, ativo=True, proxima=proxima)

    def remover(self, id_: str) -> Job:
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
