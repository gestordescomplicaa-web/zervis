"""Fila de avisos durável (Fase 7; a central de avisos do ADR 0029).

Aviso que não pode ser falado agora (conversa em andamento, a pessoa falando, aviso cortado)
espera aqui, em disco: um reinício do `jarvisd` não perde nada. Cada aviso tem prioridade
(urgente, lembrete, fim de tarefa) e, se vier de uma sessão, o nome dela, uma manchete curta
("a sessão Loja terminou") e o detalhe para quando a pessoa pedir.

Ao ficar livre, o Zé oferece: com um aviso só, fala ele; com vários, uma frase que resume e
pergunta por onde começar ("Duas novidades: a sessão Site pede aprovação e a sessão Loja
terminou. Começo pela Site?"), e a pessoa conduz ("começa", "próximo", "depois"). Avisos velhos
expiram (um lembrete de reunião que já passou não serve mais).
"""

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

VALIDADE_S = 12 * 3600
PRIORIDADES = {"urgente": 0, "lembrete": 1, "notificacao": 2}
NUMEROS = {2: "Duas", 3: "Três", 4: "Quatro", 5: "Cinco"}


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
        self.arquivo = arquivo

    def _ler(self) -> list[Aviso]:
        try:
            return _da_lista(json.loads(self.arquivo.read_text()))
        except (OSError, ValueError, TypeError):
            return []

    def _gravar(self, avisos: list[Aviso]) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporario = self.arquivo.with_suffix(".next")
        temporario.write_text(json.dumps([asdict(a) for a in avisos], ensure_ascii=False))
        temporario.chmod(0o600)
        temporario.replace(self.arquivo)

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
        avisos = [a for a in self._ler() if a.texto != texto]  # o mesmo aviso, uma vez só
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

    def validos(self, agora: float | None = None) -> list[Aviso]:
        """Os que ainda valem, na ordem de fala: prioridade, depois o mais antigo."""
        agora = time.time() if agora is None else agora
        vivos = [a for a in self._ler() if (a.expira or a.criado + VALIDADE_S) > agora]
        return sorted(vivos, key=lambda a: (a.prioridade, a.criado))

    def proximo(self, agora: float | None = None) -> Aviso | None:
        """Tira o próximo a ser ouvido (o mais urgente; entre iguais, o mais antigo)."""
        avisos = self.validos(agora)
        if not avisos:
            self._gravar([])
            return None
        self._gravar(avisos[1:])
        return avisos[0]

    def oferecer(self, agora: float | None = None) -> tuple[str, Aviso | None] | None:
        """O que dizer ao ficar livre, se houver novidade ainda não oferecida: com um aviso só,
        ele mesmo (já tirado da fila); com vários, a oferta que resume e pergunta (ficam na
        fila, marcados). None se não há nada novo."""
        avisos = self.validos(agora)
        if not avisos or all(a.oferecido for a in avisos):
            return None
        if len(avisos) == 1:
            self._gravar([])
            return avisos[0].texto, avisos[0]
        for a in avisos:
            a.oferecido = True
        self._gravar(avisos)
        return oferta(avisos), None


def oferta(avisos: list[Aviso]) -> str:
    """A frase que resume vários avisos e pergunta por onde começar (ADR 0029)."""
    n = len(avisos)
    titulos = [a.titulo or "um aviso" for a in avisos[:3]]
    if n > 3:
        titulos.append(f"mais {n - 3}")
    lista = ", ".join(titulos[:-1]) + " e " + titulos[-1]
    primeiro = avisos[0].titulo or "o primeiro"
    pelo = (
        primeiro.removeprefix("a sessão ").split(" ")[0] if primeiro.startswith("a sessão ") else ""
    )
    pergunta = f"Começo pela {pelo}?" if pelo else "Começo pelo primeiro?"
    return f"{NUMEROS.get(n, str(n))} novidades: {lista}. {pergunta}"
