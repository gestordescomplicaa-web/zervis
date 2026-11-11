"""A fala que está tocando, para o `GET /orb` (ADR 0081): o pedaço que a voz diz e até que
caractere ela chegou (`state/fala.json`, gravado por `zervis/rosto/anel.py`), para a cena do
"explicar" andar no ritmo da voz.
"""

import json
import time
from pathlib import Path
from typing import Any

VALE_S = 1.0  # mais velho que isso: a voz já parou


def atual(pasta: Path) -> dict[str, Any] | None:
    try:
        f = json.loads((pasta / "fala.json").read_text())
        if time.time() - float(f.get("ts", 0)) >= VALE_S:
            return None
        return {
            "texto": str(f.get("texto", ""))[:1500],
            "ate": int(f.get("ate", 0)),
            "inicio": float(f.get("inicio", 0)),
        }
    except (OSError, ValueError, TypeError, AttributeError):
        return None
