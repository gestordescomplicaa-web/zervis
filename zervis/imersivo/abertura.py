"""As rotas da abertura no servidor da Imersão (ADR 0078), fora do `servidor.py`:

- `GET /abertura`: o panorama do dia que o Zé grava (`abertura.json`); vazio sem ele;
- `GET /abertura/musica`: a música de abertura de quem usa; 404 sem ela (a página sintetiza);
- `POST /abertura/falar`: `{montado, passo}`; o Zé fala a fala daquele bloco do panorama
  (`passo` -1: a abertura começou; -2: foi pulada; nos dois o Zé não fala nada).
"""

import json
import re
import time
from pathlib import Path
from typing import Any

from zervis.abertura import ajustes

MONTADO = re.compile(r"[0-9T:+\-]{10,32}")


def panorama(estado: Path) -> dict[str, Any]:
    try:
        dados = json.loads((estado / "abertura.json").read_text())
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def musica(pasta: Path | None = None) -> tuple[bytes, str] | None:
    arquivo = ajustes.musica(pasta)
    if arquivo is None:
        return None
    return arquivo.read_bytes(), ajustes.TIPOS[arquivo.suffix]


def pedir_fala(estado: Path, d: dict[str, Any]) -> None:
    """Grava o pedido; recusa (ValueError) o que não for um passo de um panorama do Zé."""
    montado, passo = str(d.get("montado", "")), d.get("passo")
    if not MONTADO.fullmatch(montado) or type(passo) is not int or not -2 <= passo < 32:
        raise ValueError("pedido recusado")
    destino = estado / "abertura-falar.json"
    temporario = destino.with_suffix(".next")
    temporario.write_text(json.dumps({"montado": montado, "passo": passo, "ts": time.time()}))
    temporario.replace(destino)
