"""Baterias: assinatura do Claude e cache de cotas do OmniRoute (formato interno, falha suave)."""

import json
import sqlite3
from pathlib import Path

from zervis.cerebro.baterias import da_assinatura, do_omniroute

AGORA = 1_791_300_000.0  # 06/10/2026
ISO_AGORA = "2026-10-06T17:28:00.000Z"


def test_assinatura_mostra_a_janela_mais_apertada() -> None:
    limite = {
        "unifiedWindows": {
            "five_hour": {"utilization": 0.37, "resetsAt": AGORA + 3600},
            "seven_day": {"utilization": 0.80, "resetsAt": AGORA + 86400},
        }
    }
    b = da_assinatura(limite, AGORA)
    assert b is not None
    assert (b.restante, b.janela) == (20, "semana")
    assert b.detalhe == ("5 h: 63%", "semana: 20%")


def test_assinatura_janela_renovada_volta_a_cheia() -> None:
    limite = {"unifiedWindows": {"five_hour": {"utilization": 0.9, "resetsAt": AGORA - 1}}}
    b = da_assinatura(limite, AGORA)
    assert b is not None and b.restante == 100
    assert da_assinatura({}, AGORA) is None


def _banco(tmp_path: Path, contas: list[tuple[str, str, dict[str, object]]]) -> Path:
    banco = tmp_path / "storage.sqlite"
    con = sqlite3.connect(banco)
    con.execute("CREATE TABLE key_value (namespace TEXT, key TEXT, value TEXT)")
    con.execute("CREATE TABLE provider_connections (id TEXT, provider TEXT, is_active INTEGER)")
    for id_, provedor, cota in contas:
        con.execute("INSERT INTO provider_connections VALUES (?, ?, 1)", (id_, provedor))
        con.execute(
            "INSERT INTO key_value VALUES ('providerLimitsCache', ?, ?)", (id_, json.dumps(cota))
        )
    con.commit()
    con.close()
    return banco


def test_omniroute_por_familia_com_detalhe_por_conta(tmp_path: Path) -> None:
    futuro = "2026-10-09T22:03:24.000Z"
    banco = _banco(
        tmp_path,
        [
            (
                "a",
                "codex",
                {
                    "plan": "plus",
                    "fetchedAt": ISO_AGORA,
                    "quotas": {
                        "session": {
                            "used": 0,
                            "total": 100,
                            "resetAt": futuro,
                            "windowSeconds": 18000,
                        },
                        "weekly": {
                            "used": 88,
                            "total": 100,
                            "resetAt": futuro,
                            "windowSeconds": 604800,
                        },
                    },
                },
            ),
            (
                "b",
                "codex",
                {
                    "plan": "free",
                    "fetchedAt": ISO_AGORA,
                    "quotas": {"session": {"used": 13, "total": 100, "windowSeconds": 2592000}},
                },
            ),
            (
                "c",
                "agy",
                {
                    "plan": "Antigravity starter quota",
                    "fetchedAt": ISO_AGORA,
                    "quotas": {
                        "gemini-3.1-pro-high": {"remainingPercentage": 83.9, "resetAt": futuro},
                        "gemini-3-flash": {"remainingPercentage": 10.0, "resetAt": futuro},
                    },
                },
            ),
            ("d", "kimi-web", {"fetchedAt": ISO_AGORA, "quotas": {}}),
        ],
    )
    baterias = do_omniroute(banco, AGORA)
    assert set(baterias) == {"gpt", "gemini"}
    assert (baterias["gpt"].restante, baterias["gpt"].janela) == (12, "semana")
    assert baterias["gpt"].detalhe == ("plus: 12% (semana)", "free: 87% (mês)")
    assert baterias["gemini"].restante == 84  # o flash não é o Gemini do catálogo


def test_omniroute_velho_ou_quebrado_vira_sem_dado(tmp_path: Path) -> None:
    velho: dict[str, object] = {
        "fetchedAt": "2026-10-01T00:00:00Z",
        "quotas": {"s": {"used": 1, "total": 2}},
    }
    quebrado: dict[str, object] = {
        "fetchedAt": ISO_AGORA,
        "quotas": {"s": {"used": "x", "total": 2}},
    }
    banco = _banco(tmp_path, [("a", "codex", velho), ("b", "codex", quebrado)])
    assert do_omniroute(banco, AGORA) == {}
    assert do_omniroute(tmp_path / "nao-existe.sqlite", AGORA) == {}
