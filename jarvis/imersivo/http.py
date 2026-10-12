"""Autorização local do imersivo, compartilhada com o núcleo e os comandos de terminal."""

import os
import tempfile
from pathlib import Path

from jarvis import lugares

NOME_ARQUIVO = ".http-token"


def pasta_estado() -> Path:
    return Path(os.environ.get("ZE_IMERSIVO_ESTADO") or lugares.DADOS / "imersivo/state")


def ler_token(pasta: Path | None = None) -> str:
    try:
        return ((pasta or pasta_estado()) / NOME_ARQUIVO).read_text().strip()
    except OSError:
        return ""


def gravar_token(pasta: Path, token: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    # O temporário já nasce 0600; nunca há uma janela com o token legível por outros usuários.
    with tempfile.NamedTemporaryFile(mode="w", dir=pasta, delete=False) as arquivo:
        temporario = Path(arquivo.name)
        try:
            arquivo.write(token)
            arquivo.flush()
            temporario.replace(pasta / NOME_ARQUIVO)
        finally:
            temporario.unlink(missing_ok=True)
