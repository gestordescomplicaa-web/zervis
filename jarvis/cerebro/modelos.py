"""Os modelos que cada conta pode usar numa sessão de código (escolha na própria sessão).

O Codex guarda na pasta de cada conta a lista do que aquele plano oferece (`models_cache.json`:
modelo, nome, os níveis de esforço e o padrão); o Zé lê essa lista, sem lista fixa no código.
Conta que ainda não rodou o Codex não tem a lista: fica só o padrão da conta. O Claude Code aceita
os apelidos `opus`, `sonnet` e `haiku`, que apontam para a versão mais nova de cada um.
"""

import json
from typing import Any

from jarvis.cerebro.contas import Conta

CLAUDE = [
    {"id": "opus", "nome": "Opus", "esforcos": [], "padrao": ""},
    {"id": "sonnet", "nome": "Sonnet", "esforcos": [], "padrao": ""},
    {"id": "haiku", "nome": "Haiku", "esforcos": [], "padrao": ""},
]
ESFORCOS = {
    "low": "Baixo",
    "medium": "Médio",
    "high": "Alto",
    "xhigh": "Muito alto",
    "max": "Máximo",
    "ultra": "Ultra",
}


def do_codex(conta: Conta) -> list[dict[str, Any]]:
    """Os modelos visíveis do plano desta conta, na ordem do próprio Codex."""
    try:
        dados = json.loads((conta.onde / "models_cache.json").read_text())
    except (OSError, ValueError):
        return []
    saida = []
    for m in dados.get("models", []) if isinstance(dados, dict) else []:
        if not isinstance(m, dict) or m.get("visibility") != "list" or not m.get("slug"):
            continue
        esforcos = [
            str(e.get("effort"))
            for e in m.get("supported_reasoning_levels", [])
            if isinstance(e, dict) and e.get("effort") in ESFORCOS
        ]
        saida.append(
            {
                "id": str(m["slug"]),
                "nome": str(m.get("display_name") or m["slug"]),
                "esforcos": esforcos,
                "padrao": str(m.get("default_reasoning_level") or ""),
            }
        )
    return saida


def da_conta(conta: Conta) -> list[dict[str, Any]]:
    return do_codex(conta) if conta.agente == "codex" else list(CLAUDE)


def do_cerebro(agente: str) -> list[dict[str, Any]]:
    """Os modelos que o cérebro do Zé pode usar com a conta em uso do agente: a mesma lista das
    sessões de código."""
    from jarvis.cerebro import contas

    try:
        conta = contas.Contas().em_uso(agente)
    except contas.ContaErro:
        return list(CLAUDE) if agente == "claude" else []
    return da_conta(conta)
