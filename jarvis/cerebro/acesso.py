"""Como o Zé usa os agentes: o login que a pessoa fez em cada um, como o Orca (ADR 0015).

O Zé não faz login de assinatura nenhuma (a Anthropic proíbe produto de terceiros oferecer o login
do claude.ai). Ele procura os agentes instalados nesta máquina, o Claude Code e o Codex, e o login
de cada um; quem não tem instala e entra pelo próprio agente (`claude`, `codex login`). A chave de
API fica como alternativa, paga por uso.

Para o Claude, cérebro, voz rápida pelo plano, automações, sessões e revisão rodam o Claude Code
pelo Agent SDK, que herda o ambiente do processo. Ordem:

1. a chave de API da Anthropic colada no painel (a mesma da voz rápida): `ANTHROPIC_API_KEY`;
2. o que a máquina já tem: `ANTHROPIC_API_KEY` ou `CLAUDE_CODE_OAUTH_TOKEN` no ambiente, ou o
   login do Claude Code.
"""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jarvis.cerebro import rapido

TOKEN = "CLAUDE_CODE_OAUTH_TOKEN"  # noqa: S105 (nome da variável, não o segredo)
CHAVE = "ANTHROPIC_API_KEY"
ORIGINAL = {v: os.environ.get(v, "").strip() for v in (TOKEN, CHAVE)}
TESTE = "Responda apenas: ok"


@dataclass(frozen=True)
class Agente:
    id: str
    nome: str
    programa: str  # o comando instalado
    login: Path  # o arquivo que o próprio agente grava ao entrar
    entrar: str  # o que a pessoa roda para entrar


AGENTES = (
    Agente(
        "claude",
        "Claude",
        "claude",
        Path(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude").expanduser() / ".credentials.json",
        "claude",
    ),
    Agente(
        "codex",
        "Codex",
        "codex",
        Path(os.environ.get("CODEX_HOME") or "~/.codex").expanduser() / "auth.json",
        "codex login",
    ),
)
LOGIN = AGENTES[0].login


def _ler(arquivo: Path) -> str:
    try:
        return arquivo.read_text().strip()
    except OSError:
        return ""


def agentes(ambiente: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Os agentes desta máquina: instalado e com login (o Zé só lê; quem entra é a pessoa)."""
    ambiente = ORIGINAL if ambiente is None else ambiente
    saida = []
    for a in AGENTES:
        logado = a.login.is_file() or (a.id == "claude" and bool(ambiente.get(TOKEN)))
        saida.append(
            {
                "id": a.id,
                "nome": a.nome,
                "instalado": shutil.which(a.programa) is not None,
                "logado": logado,
                "entrar": a.entrar,
            }
        )
    return saida


def escolha(
    pasta: Path | None = None, login: Path | None = None, ambiente: dict[str, str] | None = None
) -> dict[str, str]:
    """O acesso do Claude em uso: `metodo` (chave, login ou vazio), `origem` e o segredo."""
    ambiente = ORIGINAL if ambiente is None else ambiente
    if chave := _ler(rapido.arquivo_da_chave("anthropic", pasta)):
        return {"metodo": "chave", "origem": "painel", "valor": chave}
    if ambiente.get(CHAVE):
        return {"metodo": "chave", "origem": "ambiente", "valor": ambiente[CHAVE]}
    if ambiente.get(TOKEN) or (login or LOGIN).is_file():
        return {"metodo": "login", "origem": "agente", "valor": ""}
    return {"metodo": "", "origem": "", "valor": ""}


def situacao(pasta: Path | None = None, login: Path | None = None) -> dict[str, Any]:
    """O que a tela pode saber: método, origem e os quatro últimos caracteres da chave."""
    e = escolha(pasta, login)
    return {"metodo": e["metodo"], "origem": e["origem"], "fim": e["valor"][-4:]}


def aplicar(pasta: Path | None = None, login: Path | None = None) -> str:
    """Põe a chave colada no painel no ambiente do processo; devolve o método ("" sem acesso)."""
    e = escolha(pasta, login)
    for variavel, original in ORIGINAL.items():
        if original:
            os.environ[variavel] = original
        else:
            os.environ.pop(variavel, None)
    if e["origem"] == "painel":
        os.environ[CHAVE] = e["valor"]
    return e["metodo"]


async def testar(modelo: str, pasta: Path) -> tuple[bool, str]:
    """Uma pergunta mínima ao Claude com o acesso aplicado: a prova de que o cérebro responde."""
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query

    opcoes = ClaudeAgentOptions(
        tools=[],
        allowed_tools=[],
        setting_sources=[],
        strict_mcp_config=True,
        model=modelo,
        cwd=str(pasta),
        max_turns=1,
    )
    erro: str | None = None
    respondeu = False
    try:  # até o fim do fluxo: sair no meio deixa o gerador do SDK aberto
        async for msg in query(prompt=TESTE, options=opcoes):
            if isinstance(msg, AssistantMessage) and msg.error and erro is None:
                erro = MENSAGENS.get(msg.error, "Erro do Claude.")
            elif isinstance(msg, ResultMessage):
                respondeu = not msg.is_error
    except Exception:  # o CLI caiu ou não achou credencial: para a tela, tanto faz o tipo
        return False, erro or "Sem acesso ao Claude."
    if erro or not respondeu:
        return False, erro or "Erro do Claude."
    return True, "Conectado."


MENSAGENS = {
    "authentication_failed": "Credencial inválida.",
    "billing_error": "Conta sem créditos.",
    "rate_limit": "Limite de uso atingido.",
}
