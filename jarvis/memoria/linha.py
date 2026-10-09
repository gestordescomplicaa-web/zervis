"""A linha do tempo do Zé: o que aconteceu, e quando, fora das conversas (08/10/2026).

Um evento por linha em `~/.local/share/zervis/linha-do-tempo.jsonl`, com `quando` (a hora do
fato, no fuso local) e `registrado` (a hora em que o Zé soube). O jarvisd registra sozinho o que
passa por ele (aprovações, avisos de agentes, lembretes, pedidos de manutenção, notas do dia); o
o usuário registra marcos falando ("o lançamento é dia 20", "fechei o contrato ontem"): fatos com
data, passados ou futuros, que não são lembretes. Com isso o Zé responde "o que fizemos terça?",
"quando foi que…?" e "o que tem de importante esta semana?". Nada é apagado; uma correção é um
evento novo.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from jarvis import fuso

FUSO = fuso.local()
TIPOS = {
    "marco": "marco",
    "aprovado": "aprovado",
    "aviso": "aviso",
    "lembrete": "lembrete",
    "manutencao": "manutenção",
    "nota": "nota do dia",
    "foco": "foco",
}


@dataclass(frozen=True)
class Evento:
    quando: datetime
    tipo: str
    texto: str
    registrado: datetime

    def resumo(self) -> str:
        hora = "" if (self.quando.hour, self.quando.minute) == (0, 0) else f" {self.quando:%H:%M}"
        return f"{self.quando:%d/%m/%Y}{hora} [{TIPOS.get(self.tipo, self.tipo)}] {self.texto}"


def agora() -> datetime:
    return datetime.now(FUSO)


def interpretar_data(texto: str) -> datetime:
    """`2026-10-20`, `2026-10-20 14:30` ou `20/10/2026[ 14:30]` (o cérebro converte o "dia 20")."""
    texto = texto.strip().replace("T", " ")
    for formato in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).replace(tzinfo=FUSO)
        except ValueError:
            continue
    raise ValueError(f"data que não entendi: {texto!r} (use AAAA-MM-DD ou AAAA-MM-DD HH:MM)")


class LinhaDoTempo:
    def __init__(self, arquivo: Path) -> None:
        self.arquivo = arquivo

    def registrar(self, tipo: str, texto: str, quando: datetime | None = None) -> Evento:
        if tipo not in TIPOS:
            raise ValueError(f"tipo de evento desconhecido: {tipo}")
        texto = " ".join(texto.split())[:500]
        if not texto:
            raise ValueError("evento sem texto")
        evento = Evento((quando or agora()).astimezone(FUSO), tipo, texto, agora())
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        with self.arquivo.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "quando": evento.quando.isoformat(timespec="minutes"),
                        "tipo": tipo,
                        "texto": texto,
                        "registrado": evento.registrado.isoformat(timespec="seconds"),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        return evento

    def todos(self) -> list[Evento]:
        try:
            linhas = self.arquivo.read_text().splitlines()
        except OSError:
            return []
        eventos = []
        for linha in linhas:
            try:
                d = json.loads(linha)
                eventos.append(
                    Evento(
                        datetime.fromisoformat(d["quando"]),
                        str(d["tipo"]),
                        str(d["texto"]),
                        datetime.fromisoformat(d["registrado"]),
                    )
                )
            except (ValueError, KeyError, TypeError):
                continue
        return sorted(eventos, key=lambda e: e.quando)

    def entre(self, de: datetime, ate: datetime, tipos: set[str] | None = None) -> list[Evento]:
        return [
            e for e in self.todos() if de <= e.quando < ate and (tipos is None or e.tipo in tipos)
        ]

    def proximos(self, dias: int = 7, de: datetime | None = None) -> list[Evento]:
        """Os marcos que vêm aí (os de hoje inclusive)."""
        inicio = (de or agora()).replace(hour=0, minute=0, second=0, microsecond=0)
        return self.entre(inicio, inicio + timedelta(days=dias + 1), {"marco"})
