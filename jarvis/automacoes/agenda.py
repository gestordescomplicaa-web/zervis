"""Quando uma automação roda: os quatro formatos do Hermes (docs/02-investigacao-hermes.md, 3).

- relativo, uma vez:  "em 2m", "em 1h30m", "em 45s"
- intervalo:          "a cada 30m", "a cada 2h"
- cron de 5 campos:   "cron 0 9 * * 1-5"  (minuto hora dia mês dia-da-semana; 0 = domingo)
- data e hora, uma vez: "2026-10-07 08:00" ou "2026-10-07T08:00" (no fuso de quem usa)

O cérebro traduz a fala do usuário para um desses (ele sabe a data e a hora pelo carimbo).
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from jarvis import fuso

FUSO = fuso.local()
DURACAO = re.compile(r"(?:(\d+)h)?\s*(?:(\d+)m(?:in)?)?\s*(?:(\d+)s)?")
LIMITES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]


class AgendaInvalida(ValueError):
    pass


def _duracao(texto: str) -> timedelta:
    achado = DURACAO.fullmatch(texto.replace(" ", ""))
    if not achado or not any(achado.groups()):
        raise AgendaInvalida(f"duração inválida: {texto}")
    h, m, s = (int(g or 0) for g in achado.groups())
    duracao = timedelta(hours=h, minutes=m, seconds=s)
    if duracao < timedelta(seconds=10):
        raise AgendaInvalida("duração curta demais")
    return duracao


def _campo(texto: str, minimo: int, maximo: int) -> set[int]:
    valores: set[int] = set()
    for parte in texto.split(","):
        base, _, passo_txt = parte.partition("/")
        passo = int(passo_txt) if passo_txt else 1
        if base == "*":
            inicio, fim = minimo, maximo
        elif "-" in base:
            a, b = base.split("-", 1)
            inicio, fim = int(a), int(b)
        else:
            inicio = fim = int(base)
            if passo_txt:
                fim = maximo
        if not (minimo <= inicio <= fim <= maximo) or passo < 1:
            raise AgendaInvalida(f"campo de cron fora do limite: {parte}")
        valores.update(range(inicio, fim + 1, passo))
    return valores


@dataclass(frozen=True)
class Agenda:
    texto: str
    tipo: str  # relativo, intervalo, cron, data
    repete: bool

    def _passo(self) -> str:
        return self.texto.split(" ", 2)[-1] if self.tipo == "intervalo" else self.texto[3:]

    def primeira(self, agora: datetime) -> datetime:
        """Quando roda pela primeira vez, a partir da criação."""
        if self.tipo in ("relativo", "intervalo"):
            return agora + _duracao(self._passo())
        if self.tipo == "data":
            alvo = _data(self.texto)
            if alvo <= agora:
                raise AgendaInvalida("essa data já passou")
            return alvo
        return _proximo_cron(self.texto[5:], agora)

    def seguinte(self, ultima: datetime) -> datetime | None:
        """Depois de rodar: a próxima vez, ou None se era de uma vez só."""
        if self.tipo == "intervalo":
            return ultima + _duracao(self._passo())
        if self.tipo == "cron":
            return _proximo_cron(self.texto[5:], ultima)
        return None


def _data(texto: str) -> datetime:
    try:
        alvo = datetime.fromisoformat(texto.replace(" ", "T"))
    except ValueError:
        raise AgendaInvalida(f"data inválida: {texto}") from None
    return alvo if alvo.tzinfo else alvo.replace(tzinfo=FUSO)


def _proximo_cron(expressao: str, depois: datetime) -> datetime:
    campos = expressao.split()
    if len(campos) != 5:
        raise AgendaInvalida("cron precisa de 5 campos: minuto hora dia mês dia-da-semana")
    minutos, horas, dias, meses, semana = (
        _campo(c, *limites) for c, limites in zip(campos, LIMITES, strict=True)
    )
    t = depois.astimezone(FUSO).replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(366 * 24 * 60):  # no máximo um ano à frente
        dia_semana = (t.weekday() + 1) % 7  # cron: 0 = domingo
        if (
            t.month in meses
            and t.day in dias
            and dia_semana in semana
            and t.hour in horas
            and t.minute in minutos
        ):
            return t
        t += timedelta(minutes=1)
    raise AgendaInvalida("esse cron não acontece no próximo ano")


def interpretar(texto: str) -> Agenda:
    t = " ".join(texto.strip().lower().split())
    if t.startswith("em "):
        _duracao(t[3:])
        return Agenda(t, "relativo", False)
    if t.startswith("a cada "):
        if _duracao(t[7:]) < timedelta(minutes=1):
            raise AgendaInvalida("intervalo mínimo de um minuto")
        return Agenda("a cada " + t[7:], "intervalo", True)
    if t.startswith("cron "):
        agenda = Agenda(t, "cron", True)
        _proximo_cron(t[5:], datetime.now(FUSO))
        return agenda
    _data(t)
    return Agenda(t, "data", False)
