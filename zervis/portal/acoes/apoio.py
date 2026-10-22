"""Catálogos e tradução dos dados para o painel (docs/plano-painel.md).

Só leitura do que já existe (skills, memória, automações, Foco, consumo) e, na fatia 1, as
mudanças da via rápida: motor, modelo, chave e o teste de tempo. A regra continua no núcleo;
aqui só se traduz para a tela.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from zervis import atividade, lugares

log = logging.getLogger(__name__)
DIAGNOSTICO = lugares.ESTADO / "diagnostico.md"  # o último diagnóstico, para rever na página


def linhas_do_registro() -> list[str] | None:
    """As últimas linhas do serviço no journal, sem segredos; None sem acesso ao journal."""
    try:
        r = subprocess.run(
            ["/usr/bin/journalctl", "--user", "-u", "zervis", "-n", "3000", "-o", "short-iso",
             "--no-pager"],
            capture_output=True, text=True, timeout=10, check=False,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return None
    return [
        atividade.VALOR_SECRETO.sub("•••", x)
        for x in r.stdout.splitlines()
        if not x.startswith("-- ")
    ]


MOTORES = [
    {"id": "contas", "nome": "Automático", "detalhe": "Usa as contas dos agentes.", "modelo": ""},
    {"id": "codex", "nome": "Codex", "detalhe": "Conta do Codex.", "modelo": ""},
    {
        "id": "plano",
        "nome": "Claude pelo plano",
        "detalhe": "Assinatura do Claude, sem chave.",
        "modelo": "claude-sonnet-5-5",
    },
    {
        "id": "openai",
        "nome": "OpenAI",
        "detalhe": "Chave de API da OpenAI.",
        "modelo": "gpt-5.4-mini",
    },
    {
        "id": "anthropic",
        "nome": "Anthropic",
        "detalhe": "Chave de API da Anthropic.",
        "modelo": "claude-haiku-4-5-20251001",
    },
    {
        "id": "openrouter",
        "nome": "OpenRouter",
        "detalhe": "Uma chave para muitos modelos.",
        "modelo": "openai/gpt-5.4-mini",
    },
    {
        "id": "ponte",
        "nome": "Ponte",
        "detalhe": "Qualquer serviço no formato OpenAI.",
        "modelo": "",
    },
    {
        "id": "omniroute",
        "nome": "OmniRoute",
        "detalhe": "A conexão do OmniRoute configurada no Cérebro.",
        "modelo": "",
    },
]


# Os agentes de cada camada (ADR 0015). Marca: "Claude", nunca "Claude Code".
AGENTES = [
    {"id": "claude", "nome": "Claude", "disponivel": True},
    {"id": "codex", "nome": "Codex", "disponivel": True},
    {"id": "omniroute", "nome": "OmniRoute", "disponivel": True},
]
AGENTES_SESSOES = [
    {"id": "claude", "nome": "Claude", "disponivel": True},
    {"id": "codex", "nome": "Codex", "disponivel": True},
]


def catalogo_provedor(agente: str) -> str:
    """O agente da tela no catálogo de cérebros: o OmniRoute é a opção "auto"."""
    return {"omniroute": "auto"}.get(agente, agente)


def _latencia_de_hoje(pasta: Path, dia: str) -> list[dict[str, Any]]:
    try:
        resumo = json.loads((pasta / f"{dia}-resumo.json").read_text())
    except (OSError, ValueError):
        return []
    grupos = []
    for g in resumo.get("grupos", []):
        etapas = g.get("etapas", {})
        if "total" not in etapas and "cerebro" not in etapas:
            continue
        grupos.append(
            {
                "origem": g.get("origem"),
                "provedor": g.get("provedor") or g.get("rota"),
                "turnos": g.get("turnos"),
                "cerebro_ms": (etapas.get("cerebro") or {}).get("mediana_ms"),
                "total_ms": (etapas.get("total") or {}).get("mediana_ms"),
            }
        )
    return grupos


def _ler(arquivo: Path) -> str:
    try:
        return arquivo.read_text().strip()
    except OSError:
        return ""
