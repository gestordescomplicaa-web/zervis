"""Instância única: um só processo é dono do estado (lock exclusivo)."""

import fcntl
from pathlib import Path
from typing import IO


class JaRodando(RuntimeError):
    pass


def travar(caminho: Path) -> IO[str]:
    """Devolve o arquivo travado; o lock vale enquanto ele ficar aberto."""
    caminho.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    arquivo = caminho.open("w")
    try:
        fcntl.flock(arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        arquivo.close()
        raise JaRodando(f"outro jarvisd já está rodando ({caminho})") from None
    return arquivo
