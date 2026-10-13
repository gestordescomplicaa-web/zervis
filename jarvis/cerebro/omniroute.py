"""OmniRoute como provedor (ADR 0008): o mesmo `ClaudeBrain`, com o CLI apontado para o gateway.

Nada de implementação própria de cérebro: só o ambiente do processo do CLI muda. A chave vem de
`OMNIROUTER_API_KEY` ou, sem ela, do arquivo da config (`omniroute.key`, chmod 600): só a chave,
ou um `.env` do qual só a linha `OMNIROUTER_API_KEY=` é lida; o resto do arquivo (outros segredos)
nunca entra no ambiente do Zé. Ela não é registrada em log nem copiada.
"""

import json
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jarvis import lugares

VARIAVEL_CHAVE = "OMNIROUTER_API_KEY"
# A conexão que a pessoa configurou no painel (Modelos → Cérebro → OmniRoute): o endereço do
# OmniRoute dela, local ou num servidor. A chave fica no arquivo da config (0600).
CONEXAO = lugares.CONFIG / "omniroute.json"
LOCAIS = {"127.0.0.1", "localhost", "::1"}


class OmniErro(ValueError):
    """Mensagem curta para a tela."""


def validar_endereco(endereco: str) -> str:
    """O endereço base do OmniRoute: https em qualquer lugar; http só na própria máquina (a
    chave não trafega aberta pela rede). Sem a barra final e sem o /v1."""
    endereco = endereco.strip().rstrip("/").removesuffix("/v1")
    partes = urlsplit(endereco)
    if partes.scheme == "https" and partes.hostname:
        return endereco
    if partes.scheme == "http" and partes.hostname in LOCAIS:
        return endereco
    raise OmniErro("Use https, ou http só para um OmniRoute nesta máquina.")


def ler_endereco(arquivo: Path = CONEXAO) -> str | None:
    try:
        dados = json.loads(arquivo.read_text())
        return validar_endereco(str(dados["endereco"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def gravar_conexao(endereco: str, chave: str | None, arquivo_chave: Path,
                   arquivo: Path = CONEXAO) -> None:  # fmt: skip
    endereco = validar_endereco(endereco)
    arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    arquivo.write_text(json.dumps({"endereco": endereco}))
    if chave is not None:
        chave = chave.strip()
        if not chave or len(chave) > 400 or any(c.isspace() for c in chave):
            raise OmniErro("Chave inválida.")
        temporario = arquivo_chave.with_suffix(".next")
        temporario.write_text(chave + "\n")
        temporario.chmod(0o600)
        temporario.replace(arquivo_chave)


def modelos(endereco: str, chave: str, abrir: Any = urllib.request.urlopen) -> list[str]:
    """Os modelos (e rotas) que o OmniRoute oferece, pela lista no formato OpenAI."""
    pedido = urllib.request.Request(  # noqa: S310 (endereço validado: só http/https)
        f"{validar_endereco(endereco)}/v1/models", headers={"Authorization": f"Bearer {chave}"}
    )
    try:
        with abrir(pedido, timeout=5) as resposta:
            dados = json.loads(resposta.read())
    except urllib.error.HTTPError as erro:
        if erro.code in (401, 403):
            raise OmniErro("Chave inválida.") from None
        raise OmniErro(f"O OmniRoute respondeu com erro {erro.code}.") from None
    except (OSError, ValueError):
        raise OmniErro("Sem conexão com o OmniRoute.") from None
    itens = dados.get("data", []) if isinstance(dados, dict) else []
    return sorted({str(m["id"]) for m in itens if isinstance(m, dict) and m.get("id")})


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
    porta = partes.port or (443 if partes.scheme == "https" else 80)
    try:
        with socket.create_connection((partes.hostname or "", porta), limite_s):
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
