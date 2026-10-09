"""Estado da máquina para "como está o computador?" (risco 0; docs/07-sistema-omarchy.md).

Junta o que o Omarchy já mede (CPU, rede, atualização, bateria) com o que o Linux expõe (memória
disponível de verdade, swap, disco, tempo ligado) e os processos que mais pesam. Os processos de
agente antigos (Codex e Claude abertos há dias) aparecem à parte: já consumiram muita RAM sem
ninguém do outro lado (06/10/2026).
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any

AGENTES = ("codex", "claude")
VELHO_H = 48


def _omarchy(nome: str) -> str:
    try:
        feito = subprocess.run(  # noqa: S603 (comando fixo do Omarchy)
            [f"/usr/bin/omarchy-{nome}"],
            capture_output=True, text=True, timeout=8, stdin=subprocess.DEVNULL, check=False,
        )  # fmt: skip
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return " ".join(feito.stdout.split())


def _meminfo() -> dict[str, int]:
    campos = {}
    for linha in Path("/proc/meminfo").read_text().splitlines():
        chave, _, valor = linha.partition(":")
        campos[chave] = int(valor.split()[0]) // 1024  # MB
    return campos


def processos() -> list[dict[str, Any]]:
    feito = subprocess.run(
        ["/usr/bin/ps", "-eo", "pcpu=,rss=,etimes=,comm=", "--sort=-pcpu"],
        capture_output=True, text=True, timeout=5, check=False,
    )  # fmt: skip
    lista = []
    for linha in feito.stdout.splitlines():
        partes = linha.split(None, 3)
        if len(partes) == 4:
            lista.append(
                {
                    "nome": partes[3],
                    "cpu": float(partes[0]),
                    "ram_mb": int(partes[1]) // 1024,
                    "horas": int(partes[2]) // 3600,
                }
            )
    return lista


def estado() -> dict[str, Any]:
    mem = _meminfo()
    disco = shutil.disk_usage(Path.home())
    todos = processos()
    agentes_velhos = [
        p for p in todos if p["nome"] in AGENTES and p["horas"] >= VELHO_H and p["ram_mb"] > 50
    ]
    segundos = float(Path("/proc/uptime").read_text().split()[0])
    return {
        "cpu_e_memoria": _omarchy("system-stats"),
        "memoria_disponivel_gb": round(mem.get("MemAvailable", 0) / 1024, 1),
        "memoria_total_gb": round(mem.get("MemTotal", 0) / 1024, 1),
        "swap_usado_gb": round((mem.get("SwapTotal", 0) - mem.get("SwapFree", 0)) / 1024, 1),
        "disco_livre_gb": round(disco.free / 1e9),
        "disco_total_gb": round(disco.total / 1e9),
        "ligado_ha_horas": round(segundos / 3600, 1),
        "rede": _omarchy("network-status") or "sem dado",
        "atualizacao": _omarchy("update-available") or "sem dado",
        "bateria": _omarchy("battery-status") or "sem bateria (desktop)",
        "mais_cpu": sorted(todos, key=lambda p: -p["cpu"])[:5],
        "mais_ram": sorted(todos, key=lambda p: -p["ram_mb"])[:5],
        "agentes_abertos_ha_dias": agentes_velhos,
    }
