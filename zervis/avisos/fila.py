"""Fila de avisos durável (Fase 7; a central de avisos do ADR 0029).

Aviso que não pode ser falado agora (conversa em andamento, a pessoa falando, aviso cortado)
espera aqui, em SQLite (`avisos.db`): um reinício do `jarvisd` não perde nada. Cada aviso tem
prioridade (urgente, lembrete, fim de tarefa) e, se vier de uma sessão, o nome dela, uma
manchete curta ("a sessão Loja terminou") e o detalhe para quando a pessoa pedir.

Avisos de sessão saem um por vez, automaticamente, na ordem de prioridade. Outros avisos
acumulados podem virar uma oferta. Avisos velhos expiram (um lembrete que passou não serve).
"""

import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from zervis.dados.lista import Lista

VALIDADE_S = 12 * 3600
PRIORIDADES = {"urgente": 0, "lembrete": 1, "notificacao": 2}
NUMEROS = {2: "Duas", 3: "Três", 4: "Quatro", 5: "Cinco"}
_TRAVAS: dict[Path, threading.RLock] = {}
_CRIAR_TRAVA = threading.Lock()


@dataclass
class Aviso:
    texto: str
    origem: str = "jarvis"  # automação, agenda, oficina, revisão...
    expira: float = 0.0  # epoch; 0 = validade padrão
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    criado: float = field(default_factory=time.time)
    prioridade: int = 2  # 0 urgente, 1 lembrete, 2 fim de tarefa e o resto
    titulo: str = ""  # a manchete na oferta: "a sessão Loja terminou", "um lembrete"
    sessao: str = ""  # id da sessão que avisou, para ficar em foco ao ser ouvido
    detalhe: str = ""  # o que a sessão disse, pronto para ouvir, se a pessoa pedir
    oferecido: bool = False  # já entrou numa oferta: não é oferecido sozinho de novo


def _da_lista(brutos: Any) -> list[Aviso]:
    campos = set(Aviso.__dataclass_fields__)
    return [
        Aviso(**{k: v for k, v in a.items() if k in campos})
        for a in brutos
        if isinstance(a, dict) and "texto" in a
    ]


class Fila:
    def __init__(self, arquivo: Path) -> None:
        self._lista = Lista(arquivo, "avisos")
        self.arquivo = self._lista.arquivo
        with _CRIAR_TRAVA:
            self._trava = _TRAVAS.setdefault(self.arquivo.resolve(), threading.RLock())

    def _ler(self) -> list[Aviso]:
        return _da_lista(self._lista.ler())

    def _gravar(self, avisos: list[Aviso]) -> None:
        self._lista.gravar([asdict(a) for a in avisos])

    def guardar(
        self,
        texto: str,
        origem: str = "jarvis",
        expira: float = 0.0,
        prioridade: int = 2,
        titulo: str = "",
        sessao: str = "",
        detalhe: str = "",
    ) -> None:
        with self._trava, self._lista.transacao():
            avisos = [a for a in self._ler() if (a.texto, a.sessao) != (texto, sessao)]
            avisos.append(
                Aviso(
                    texto,
                    origem,
                    expira,
                    prioridade=prioridade,
                    titulo=titulo,
                    sessao=sessao,
                    detalhe=detalhe,
                )
            )
            self._gravar(avisos)

    def remover(self, texto: str, sessao: str = "") -> None:
        """Tira um aviso que deixou de valer (uma pergunta já respondida em outro lugar)."""
        with self._trava, self._lista.transacao():
            avisos = self._ler()
            if any((a.texto, a.sessao) == (texto, sessao) for a in avisos):
                self._gravar([a for a in avisos if (a.texto, a.sessao) != (texto, sessao)])

    def validos(self, agora: float | None = None) -> list[Aviso]:
        """Os que ainda valem, na ordem de fala: prioridade, depois o mais antigo."""
        with self._trava, self._lista.transacao():
            agora = time.time() if agora is None else agora
            vivos = [a for a in self._ler() if (a.expira or a.criado + VALIDADE_S) > agora]
            return sorted(vivos, key=lambda a: (a.prioridade, a.criado))

    def proximo(self, agora: float | None = None) -> Aviso | None:
        """Tira o próximo a ser ouvido (o mais urgente; entre iguais, o mais antigo)."""
        with self._trava, self._lista.transacao():
            avisos = self.validos(agora)
            if not avisos:
                self._gravar([])
                return None
            self._gravar(avisos[1:])
            return avisos[0]

    def oferecer(self, agora: float | None = None) -> tuple[str, Aviso | None] | None:
        """Sessões saem individualmente; não dependem de 'começa' ou 'próximo'."""
        with self._trava, self._lista.transacao():
            avisos = self.validos(agora)
            if not avisos:
                return None
            if any(a.sessao for a in avisos):
                self._gravar(avisos[1:])
                return avisos[0].texto, avisos[0]
            if all(a.oferecido for a in avisos):
                return None
            if len(avisos) == 1:
                self._gravar([])
                return avisos[0].texto, avisos[0]
            for a in avisos:
                a.oferecido = True
            self._gravar(avisos)
            return oferta(avisos), None


MAIS = {1: "mais um aviso", 2: "mais dois avisos", 3: "mais três avisos"}


def oferta(avisos: list[Aviso]) -> str:
    """A frase que resume vários avisos e pergunta por onde começar (ADR 0029). Os sem manchete
    viram uma conta só ("e mais dois avisos"), nunca "um aviso, um aviso e um aviso"."""
    n = len(avisos)
    titulos = [a.titulo for a in avisos if a.titulo][:3]
    if not titulos:
        return f"{NUMEROS.get(n, str(n))} novidades esperando. Começo pela primeira?"
    if resto := n - len(titulos):
        titulos.append(MAIS.get(resto, f"mais {resto} avisos"))
    lista = ", ".join(titulos[:-1]) + " e " + titulos[-1]
    primeiro = avisos[0].titulo or "o primeiro"
    pelo = (
        primeiro.removeprefix("a sessão ").split(" ")[0] if primeiro.startswith("a sessão ") else ""
    )
    pergunta = f"Começo pela {pelo}?" if pelo else "Começo pelo primeiro?"
    return f"{NUMEROS.get(n, str(n))} novidades: {lista}. {pergunta}"
