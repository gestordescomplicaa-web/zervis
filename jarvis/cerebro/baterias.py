"""Bateria de cada família de cérebro: quanto ainda resta da cota, de 0 a 100 (ADR 0010).

- Claude: o `RateLimitEvent` que chega a cada resposta da assinatura (janelas de 5 h e semana).
- GPT e Gemini: o cache que o próprio OmniRoute atualiza sozinho para cada conta conectada
  (`providerLimitsCache` no `storage.sqlite` dele), lido só para consulta. É um formato interno
  do OmniRoute: qualquer surpresa vira "sem dado", nunca erro no JARVIS.

A bateria da família é a da janela mais apertada entre as contas dela; o detalhe por conta
(sem e-mail) vai junto para a dica do Barehands.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)
JANELAS = {18000: "5 h", 86400: "dia", 604800: "semana", 2592000: "mês"}
VELHO_S = 3 * 3600  # cache do OmniRoute mais velho que isso não vale
PROVEDOR_FAMILIA = {"codex": "gpt", "agy": "gemini"}
MODELO_GEMINI = "gemini-3.1-pro"  # o Gemini do catálogo; as outras cotas do Antigravity não contam


@dataclass(frozen=True)
class Bateria:
    restante: int  # 0..100
    janela: str  # "5 h", "semana"...: a que está mais apertada
    renova: float | None = None  # epoch
    detalhe: tuple[str, ...] = field(default_factory=tuple)


def _restante(usado: float, total: float) -> int:
    return max(0, min(100, round(100 * (1 - usado / total)))) if total > 0 else 0


def da_assinatura(limite: dict[str, Any], agora: float) -> Bateria | None:
    janelas = limite.get("unifiedWindows") or {}
    candidatas = []
    for nome, rotulo in (("five_hour", "5 h"), ("seven_day", "semana")):
        janela = janelas.get(nome) or {}
        uso, renova = janela.get("utilization"), janela.get("resetsAt")
        if uso is None:
            continue
        if renova is not None and renova <= agora:
            uso = 0.0  # a janela já renovou desde o último aviso
        candidatas.append(Bateria(_restante(uso, 1.0), rotulo, renova))
    if not candidatas:
        return None
    pior = min(candidatas, key=lambda b: b.restante)
    detalhe = tuple(f"{b.janela}: {b.restante}%" for b in candidatas)
    return Bateria(pior.restante, pior.janela, pior.renova, detalhe)


def _epoch(texto: Any) -> float | None:
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _janelas_da_conta(provedor: str, cota: dict[str, Any], agora: float) -> list[Bateria]:
    janelas = []
    for nome, q in (cota.get("quotas") or {}).items():
        if not isinstance(q, dict) or q.get("unlimited"):
            continue
        if provedor == "agy" and not str(nome).startswith(MODELO_GEMINI):
            continue
        renova = _epoch(q.get("resetAt"))
        if renova is not None and renova <= agora:
            restante = 100
        elif "remainingPercentage" in q:
            restante = max(0, min(100, round(float(q["remainingPercentage"]))))
        else:
            restante = _restante(float(q["used"]), float(q["total"]))
        rotulo = JANELAS.get(int(q.get("windowSeconds") or 0), "cota")
        janelas.append(Bateria(restante, rotulo, renova))
    return janelas


def do_omniroute(banco: Path, agora: float) -> dict[str, Bateria]:
    try:
        con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True, timeout=1)
        try:
            linhas = con.execute(
                "SELECT c.provider, k.value FROM key_value k "
                "JOIN provider_connections c ON c.id = k.key "
                "WHERE k.namespace = 'providerLimitsCache' AND c.is_active = 1"
            ).fetchall()
        finally:
            con.close()
    except sqlite3.Error as erro:
        log.info("cotas do OmniRoute indisponíveis: %s", erro)
        return {}
    por_familia: dict[str, list[tuple[str, Bateria]]] = {}
    for provedor, valor in linhas:
        familia = PROVEDOR_FAMILIA.get(provedor)
        if familia is None:
            continue
        try:
            cota = json.loads(valor)
            if agora - (_epoch(cota.get("fetchedAt")) or 0) > VELHO_S:
                continue
            janelas = _janelas_da_conta(provedor, cota, agora)
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
        if janelas:
            pior = min(janelas, key=lambda b: b.restante)
            plano = str(cota.get("plan") or provedor).split()[0].lower()
            por_familia.setdefault(familia, []).append((plano, pior))
    baterias = {}
    for familia, contas in por_familia.items():
        _, pior = min(contas, key=lambda c: c[1].restante)
        detalhe = tuple(f"{plano}: {b.restante}% ({b.janela})" for plano, b in contas)
        baterias[familia] = Bateria(pior.restante, pior.janela, pior.renova, detalhe)
    return baterias
