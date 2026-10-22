"""Lembretes de reunião da agenda do Omarchy (portado de VIBE-CODING/hermes-monitor/
calendar_monitor.py, 06/10/2026; a agenda estava sem dono desde que o monitor foi desligado).

Lê o cache que o Omarchy mantém (`~/.local/state/omarchy/calendar-events.json`). Avisa 15 e 5
minutos antes (quem começa dentro de 5 minutos ganha só o de 5). Ignora dia inteiro, cancelado,
recusado e eventos de local de trabalho ou ausência. Agenda sem sincronizar há mais de 20 minutos
não gera aviso: melhor calar do que avisar reunião que mudou.
"""

import hashlib
import json
import math
import time
from datetime import datetime
from pathlib import Path

CACHE = Path.home() / ".local/state/omarchy/calendar-events.json"
VALIDADE_CACHE_S = 20 * 60
ANTECEDENCIAS = (15, 5)


def _epoch(valor: str) -> float:
    data = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    if data.tzinfo is None:
        raise ValueError("horário da agenda sem fuso")
    return data.timestamp()


def eventos(cache: Path = CACHE, agora: float | None = None) -> list[dict[str, object]]:
    """Eventos válidos, em ordem; lista vazia se a agenda estiver velha ou ilegível."""
    agora = time.time() if agora is None else agora
    try:
        pacote = json.loads(cache.read_text())
        if pacote.get("version") != 1 or agora - _epoch(pacote["syncedAt"]) > VALIDADE_CACHE_S:
            return []
        brutos = pacote["events"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    lista = []
    for e in brutos:
        if (
            e.get("allDay")
            or e.get("status") == "cancelled"
            or e.get("responseStatus") == "declined"
            or e.get("eventType") in ("workingLocation", "outOfOffice")
        ):
            continue
        try:
            inicio = _epoch(e["start"])
        except (KeyError, ValueError):
            continue
        titulo = " ".join(str(e.get("title") or "Compromisso sem título").split())[:120]
        lista.append({"id": str(e.get("id", "")), "inicio": inicio, "titulo": titulo})
    return sorted(lista, key=lambda e: float(e["inicio"]))  # type: ignore[arg-type]


class Calendario:
    def __init__(self, enviados: Path, cache: Path = CACHE) -> None:
        self.enviados = enviados
        self.cache = cache

    def _carregar(self) -> dict[str, float]:
        try:
            dados = json.loads(self.enviados.read_text())
        except (OSError, ValueError):
            return {}
        return dados if isinstance(dados, dict) else {}

    def vencidos(self, agora: float | None = None) -> list[tuple[str, float]]:
        """(texto do aviso, quando expira) dos lembretes que chegaram na hora; cada um uma vez."""
        agora = time.time() if agora is None else agora
        enviados = {k: v for k, v in self._carregar().items() if v > agora - 7 * 86400}
        avisos = []
        for e in eventos(self.cache, agora):
            inicio = float(e["inicio"])  # type: ignore[arg-type]
            faltam = inicio - agora
            if not 0 < faltam <= max(ANTECEDENCIAS) * 60:
                continue
            antecedencia = min(a for a in ANTECEDENCIAS if faltam <= a * 60)
            chave = hashlib.sha256(f"{e['id']}|{inicio}|{antecedencia}".encode()).hexdigest()[:16]
            if chave in enviados:
                continue
            enviados[chave] = inicio
            minutos = max(1, math.ceil(faltam / 60))
            avisos.append((f"Daqui a {minutos} minutos: {e['titulo']}.", inicio))
        temporario = self.enviados.with_suffix(".next")
        temporario.write_text(json.dumps(enviados))
        temporario.replace(self.enviados)
        return avisos
