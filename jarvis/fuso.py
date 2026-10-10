"""O fuso de quem usa o Zé: `JARVIS_FUSO`, o do perfil, `TZ` ou o do sistema; UTC se nada servir.

Nada de fuso fixo no código: a hora das automações, das conversas e da linha do tempo é a da
máquina onde o Zé roda (no Linux, `/etc/localtime` aponta para o fuso escolhido na instalação).
"""

import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from jarvis import usuario


def _do_sistema() -> str:
    try:
        alvo = str(Path("/etc/localtime").resolve())
    except OSError:
        alvo = ""
    if "zoneinfo/" in alvo:
        return alvo.split("zoneinfo/", 1)[1]
    try:
        return Path("/etc/timezone").read_text().strip()
    except OSError:
        return ""


def _primeiro(*nomes: str) -> ZoneInfo:
    for nome in nomes:
        nome = nome.strip().lstrip(":")
        if not nome:
            continue
        try:
            return ZoneInfo(nome)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return ZoneInfo("UTC")


def do_sistema() -> ZoneInfo:
    """O fuso da máquina, sem a escolha do perfil (o padrão que o painel sugere)."""
    return _primeiro(os.environ.get("TZ", ""), _do_sistema())


def local() -> ZoneInfo:
    return _primeiro(
        os.environ.get("JARVIS_FUSO", ""),
        usuario.ler().fuso,
        os.environ.get("TZ", ""),
        _do_sistema(),
    )


def valido(nome: str) -> bool:
    return nome in nomes()


def nomes() -> list[str]:
    fusos = (n for n in available_timezones() if "/" in n and not n.startswith("Etc/"))
    return ["UTC", *sorted(fusos)]
