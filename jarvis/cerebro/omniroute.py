"""OmniRoute como provedor (ADR 0008): o mesmo `ClaudeBrain`, com o CLI apontado para o gateway.

Nada de implementação própria de cérebro: só o ambiente do processo do CLI muda. A chave vem de
`OMNIROUTER_API_KEY` ou, sem ela, do arquivo da config (`omniroute.key`, chmod 600): só a chave,
ou um `.env` do qual só a linha `OMNIROUTER_API_KEY=` é lida; o resto do arquivo (outros segredos)
nunca entra no ambiente do Zé. Ela não é registrada em log nem copiada.
"""

import os
import socket
from pathlib import Path
from urllib.parse import urlsplit

VARIAVEL_CHAVE = "OMNIROUTER_API_KEY"


def ler_chave(arquivo: Path) -> str | None:
    if valor := os.environ.get(VARIAVEL_CHAVE, "").strip():
        return valor
    try:
        linhas = arquivo.read_text().splitlines()
    except OSError:
        return None
    uteis = [linha.strip() for linha in linhas if linha.strip() and not linha.startswith("#")]
    if len(uteis) == 1 and "=" not in uteis[0]:
        return uteis[0]
    for linha in linhas:
        nome, _, valor = linha.removeprefix("export ").partition("=")
        if nome.strip() == VARIAVEL_CHAVE:
            return valor.strip().strip("\"'") or None
    return None


def no_ar(endereco: str, limite_s: float = 1.0) -> bool:
    """O serviço aceita conexão? Só isso; a chave é conferida pelo próprio pedido."""
    partes = urlsplit(endereco)
    try:
        with socket.create_connection((partes.hostname or "", partes.port or 80), limite_s):
            return True
    except OSError:
        return False


def ambiente(endereco: str, chave: str, rota: str) -> dict[str, str]:
    """Ambiente do CLI do Claude Code para falar com o OmniRoute em vez da assinatura."""
    return {
        "ANTHROPIC_BASE_URL": endereco,
        "ANTHROPIC_AUTH_TOKEN": chave,
        "ANTHROPIC_API_KEY": "",
        "ANTHROPIC_SMALL_FAST_MODEL": rota,
        # Conexão local: nunca por proxy do ambiente.
        "NO_PROXY": "127.0.0.1,localhost,::1",
    }
