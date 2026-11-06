"""As ligações do WhatsApp que o agente atendeu: quem, quando, quanto durou, o resumo e o que foi
dito (06/11/2026). Antes, o Zé só sabia que houve uma ligação: "o que falaram na ligação?" ficava
sem resposta. Fica nos dados do Zé, as mais recentes; o texto é de terceiros, dado.
"""

import contextlib
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from zervis.avisos.caixa import ident
from zervis.avisos.pendentes import candidatos
from zervis.dados.lista import Lista

GUARDADAS = 200


@dataclass
class Ligacao:
    id: str
    quando: float
    telefone: str
    nome: str
    duracao: int  # segundos
    desfecho: str  # normal, passou, limite, silencio, falha
    resumo: str
    conversa: list[dict[str, str]] = field(default_factory=list)
    direcao: str = "recebida"  # ou "feita": o Zé ligou para dar um recado seu (ADR 0067)

    @property
    def quem(self) -> str:
        if self.nome:
            return self.nome
        return f"o número {numero_falado(self.telefone)}" if self.telefone else "um número oculto"


def numero_falado(telefone: str) -> str:
    """Para falar e para a pergunta da aprovação: "11 98765-4321" (do Brasil) ou "+1 4155551234"."""
    if telefone.startswith("55") and len(telefone) in (12, 13):
        local = telefone[4:]
        return f"{telefone[2:4]} {local[:-4]}-{local[-4:]}"
    return f"+{telefone}"


def duracao_falada(segundos: int) -> str:
    minutos = round(segundos / 60)
    if minutos < 1:
        return "menos de um minuto"
    return "um minuto" if minutos == 1 else f"{minutos} minutos"


class Ligacoes:
    def __init__(self, arquivo: Path, agora: Callable[[], float] = time.time) -> None:
        self._banco = Lista(arquivo, "ligacoes")  # SQLite; importa o JSON de antes
        self.arquivo = self._banco.arquivo
        self.agora = agora
        self._trava = threading.Lock()

    def _ler(self) -> list[Ligacao]:
        lista = []
        for d in self._banco.ler():
            with contextlib.suppress(TypeError):
                lista.append(Ligacao(**d))
        return lista

    def registrar(self, evento: dict[str, Any], direcao: str = "recebida") -> Ligacao:
        quando = float(evento.get("quando") or self.agora())
        telefone = str(evento.get("telefone", ""))
        conversa = [
            {"quem": str(f.get("quem", "")), "texto": str(f.get("texto", ""))[:2000]}
            for f in evento.get("conversa") or []
            if isinstance(f, dict)
        ]
        lig = Ligacao(
            ident(f"{telefone}:{quando}"),
            quando,
            telefone,
            " ".join(str(evento.get("nome", "")).split())[:80],
            int(evento.get("duracao") or 0),
            str(evento.get("desfecho") or evento.get("resultado") or ""),
            " ".join(str(evento.get("resumo", "")).split())[:600],
            conversa,
            direcao,
        )
        with self._trava, self._banco.transacao():
            lista = [x for x in self._ler() if x.id != lig.id] + [lig]
            self._banco.gravar([asdict(x) for x in lista[-GUARDADAS:]])
        return lig

    def recentes(self, quantas: int = 10) -> list[Ligacao]:
        return list(reversed(self._ler()))[:quantas]

    def achar(self, quem: str) -> list[Ligacao]:
        """As ligações de quem foi pedido (pelo id, o nome ou os últimos dígitos), a mais nova
        primeiro."""
        quem = " ".join(quem.split())
        todas = self.recentes(GUARDADAS)
        if not quem:
            return []
        if por_id := [x for x in todas if x.id == quem]:
            return por_id
        digitos = "".join(c for c in quem if c.isdigit())
        if len(digitos) >= 4 and len(digitos) == len(quem.replace(" ", "").replace("-", "")):
            return [x for x in todas if x.telefone.endswith(digitos)]
        nomes = candidatos([todas], quem, lambda x: (x.nome, x.telefone))
        chaves = {(x.nome, x.telefone) for x in nomes}
        return [x for x in todas if (x.nome, x.telefone) in chaves]
