"""Como o Zé entra no Claude: assinatura ou chave de API (configuração da primeira vez, 09/10/2026).

Cérebro principal, via rápida pelo plano, automações, sessões e revisão usam o CLI do Claude Code
pelo Agent SDK, e o CLI herda o ambiente do processo. Por isso o acesso se aplica uma vez, no
ambiente, e vale para todos. Ordem:

1. token da assinatura colado no painel (`claude setup-token`): `CLAUDE_CODE_OAUTH_TOKEN`;
2. chave de API da Anthropic colada no painel (a mesma da via rápida): `ANTHROPIC_API_KEY`;
3. o que a máquina já tem: essas variáveis no ambiente ou o login do Claude Code.

O que foi colado no painel vence: foi escolhido de propósito. Com o token, uma `ANTHROPIC_API_KEY`
do ambiente sai do processo, porque o CLI daria preferência a ela.
"""

import os
from pathlib import Path
from typing import Any

from jarvis.cerebro import rapido

TOKEN = "CLAUDE_CODE_OAUTH_TOKEN"  # noqa: S105 (nome da variável, não o segredo)
CHAVE = "ANTHROPIC_API_KEY"
ORIGINAL = {v: os.environ.get(v, "").strip() for v in (TOKEN, CHAVE)}
LOGIN = Path(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude").expanduser() / ".credentials.json"
TESTE = "Responda apenas: ok"


def arquivo_do_token(pasta: Path | None = None) -> Path:
    return (pasta or rapido.CHAVES) / "claude.token"


def _ler(arquivo: Path) -> str:
    try:
        return arquivo.read_text().strip()
    except OSError:
        return ""


def escolha(
    pasta: Path | None = None, login: Path | None = None, ambiente: dict[str, str] | None = None
) -> dict[str, str]:
    """O acesso em uso: `metodo` (assinatura, chave ou vazio), `origem` e o segredo (`valor`)."""
    ambiente = ORIGINAL if ambiente is None else ambiente
    if token := _ler(arquivo_do_token(pasta)):
        return {"metodo": "assinatura", "origem": "painel", "valor": token}
    if chave := _ler(rapido.arquivo_da_chave("anthropic", pasta)):
        return {"metodo": "chave", "origem": "painel", "valor": chave}
    if ambiente.get(TOKEN):
        return {"metodo": "assinatura", "origem": "ambiente", "valor": ambiente[TOKEN]}
    if ambiente.get(CHAVE):
        return {"metodo": "chave", "origem": "ambiente", "valor": ambiente[CHAVE]}
    if (login or LOGIN).is_file():
        return {"metodo": "assinatura", "origem": "login", "valor": ""}
    return {"metodo": "", "origem": "", "valor": ""}


def situacao(pasta: Path | None = None, login: Path | None = None) -> dict[str, Any]:
    """O que a tela pode saber: método, origem e os quatro últimos caracteres do segredo."""
    e = escolha(pasta, login)
    return {"metodo": e["metodo"], "origem": e["origem"], "fim": e["valor"][-4:]}


def aplicar(pasta: Path | None = None, login: Path | None = None) -> str:
    """Põe o acesso escolhido no ambiente do processo; devolve o método ("" sem acesso)."""
    e = escolha(pasta, login)
    for variavel, original in ORIGINAL.items():
        if original:
            os.environ[variavel] = original
        else:
            os.environ.pop(variavel, None)
    if e["origem"] == "painel" and e["metodo"] == "assinatura":
        os.environ[TOKEN] = e["valor"]
        os.environ.pop(CHAVE, None)
    elif e["origem"] == "painel":
        os.environ[CHAVE] = e["valor"]
    return e["metodo"]


def gravar_token(token: str, pasta: Path | None = None) -> None:
    token = token.strip()
    if not token or len(token) > 400 or any(c.isspace() for c in token):
        raise ValueError("token vazio ou com espaços")
    destino = arquivo_do_token(pasta)
    destino.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporario = destino.with_suffix(".next")
    temporario.touch(mode=0o600)
    temporario.chmod(0o600)
    temporario.write_text(token + "\n")
    temporario.replace(destino)


def apagar_token(pasta: Path | None = None) -> None:
    arquivo_do_token(pasta).unlink(missing_ok=True)


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
