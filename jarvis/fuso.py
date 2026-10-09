"""O fuso de quem usa o Zé: `JARVIS_FUSO`, senão `TZ`, senão o do sistema; UTC se nada servir.

Nada de fuso fixo no código: a hora das automações, das conversas e da linha do tempo é a da
máquina onde o Zé roda (no Linux, `/etc/localtime` aponta para o fuso escolhido na instalação).
"""

import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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


def local() -> ZoneInfo:
    for nome in (os.environ.get("JARVIS_FUSO", ""), os.environ.get("TZ", ""), _do_sistema()):
        nome = nome.strip().lstrip(":")
        if not nome:
            continue
        try:
            return ZoneInfo(nome)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return ZoneInfo("UTC")
