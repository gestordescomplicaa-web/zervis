"""Fila de avisos durável (Fase 7; portada da ideia de VIBE-CODING/jarvis/notices.py).

Aviso que não pode ser falado agora (janela fechada, conversa em andamento, aviso cortado por um
"Hey Orca") espera aqui, em disco: um reinício do `jarvisd` não perde nada. Ao ficar ATIVO, sai um
aviso só; se houver vários, um resumo único ("Enquanto você estava fora: …"). Avisos velhos
expiram (um lembrete de reunião que já passou não serve mais).
"""

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

VALIDADE_S = 12 * 3600
MAXIMO_NO_RESUMO = 5


@dataclass
class Aviso:
    texto: str
    origem: str = "jarvis"  # automação, agenda, oficina, revisão...
    expira: float = 0.0  # epoch; 0 = validade padrão
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    criado: float = field(default_factory=time.time)


class Fila:
    def __init__(self, arquivo: Path) -> None:
        self.arquivo = arquivo

    def _ler(self) -> list[Aviso]:
        try:
            brutos = json.loads(self.arquivo.read_text())
        except (OSError, ValueError):
            return []
        return [Aviso(**a) for a in brutos if isinstance(a, dict)]

    def _gravar(self, avisos: list[Aviso]) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporario = self.arquivo.with_suffix(".next")
        temporario.write_text(json.dumps([asdict(a) for a in avisos], ensure_ascii=False))
        temporario.chmod(0o600)
        temporario.replace(self.arquivo)

    def guardar(self, texto: str, origem: str = "jarvis", expira: float = 0.0) -> None:
        self._gravar([*self._ler(), Aviso(texto, origem, expira)])

    def validos(self, agora: float | None = None) -> list[Aviso]:
        agora = time.time() if agora is None else agora
        return [a for a in self._ler() if (a.expira or a.criado + VALIDADE_S) > agora]

    def tirar_tudo(self, agora: float | None = None) -> str | None:
        """O que falar ao ficar ativo: um aviso, um resumo de vários, ou None. Esvazia a fila."""
        avisos = self.validos(agora)
        self._gravar([])
        if not avisos:
            return None
        if len(avisos) == 1:
            return avisos[0].texto
        partes = [a.texto.rstrip(".") for a in avisos[:MAXIMO_NO_RESUMO]]
        resto = len(avisos) - len(partes)
        fim = f" E mais {resto} avisos." if resto else ""
        return f"Enquanto isso, {len(avisos)} avisos: " + "; ".join(partes) + "." + fim
