"""O cérebro do agente de atendimento: o modelo que responde no texto e nas ligações.

Escolhido na página Atendimento, como o modelo de uma sessão de código: as mesmas contas do Zé
(Claude e Codex pela assinatura) e as chaves de API guardadas na via rápida (Modelos). Numa
ligação, cada segundo conta: com chave de API o modelo fala direto com o serviço, como no
Ligatia, e começa a responder em frações de segundo; pela assinatura passa pelo agente da conta
e leva dois a três segundos.
"""

import shutil
from pathlib import Path
from typing import Any

from jarvis.cerebro import modelos, rapido

PADRAO = {"motor": "plano", "modelo": "claude-haiku-4-5-20251001"}
ASSINATURAS = ("plano", "codex")
# Os modelos rápidos de cada chave de API (o primeiro é o sugerido para ligações).
API = {
    "anthropic": [
        ("claude-haiku-4-5-20251001", "Haiku 4.5"),
        ("claude-sonnet-5-5", "Sonnet 5.5"),
    ],
    "openai": [("gpt-5.4-mini", "GPT-5.4 mini")],
    "openrouter": [("openai/gpt-5.4-mini", "GPT-5.4 mini")],
}
NOMES_API = {"anthropic": "Anthropic", "openai": "OpenAI", "openrouter": "OpenRouter"}
MAX_TOKENS = 400


def tem_chave(motor: str) -> bool:
    return rapido.ler_chave(motor, "") is not None


def opcoes() -> list[dict[str, Any]]:
    """Os grupos da escolha na página: valor "motor|modelo", nome e detalhe."""
    grupos = [
        {
            "titulo": "Claude · assinatura",
            "itens": [
                {
                    "valor": f"plano|{m['id']}",
                    "nome": m["nome"],
                    "detalhe": "Sem chave. 2 a 3 s nas ligações.",
                }
                for m in modelos.CLAUDE
            ],
        }
    ]
    if shutil.which("codex"):
        codex = modelos.do_cerebro("codex")
        if codex:
            grupos.append(
                {
                    "titulo": "Codex · assinatura",
                    "itens": [
                        {"valor": f"codex|{m['id']}", "nome": m["nome"], "detalhe": "Sem chave."}
                        for m in codex
                    ],
                }
            )
    for motor, lista in API.items():
        if tem_chave(motor):
            grupos.append(
                {
                    "titulo": f"{NOMES_API[motor]} · chave de API",
                    "itens": [
                        {
                            "valor": f"{motor}|{mid}",
                            "nome": nome,
                            "detalhe": "Mais rápido nas ligações.",
                        }
                        for mid, nome in lista
                    ],
                }
            )
    return grupos


def validar(valor: Any) -> dict[str, str]:
    """ "motor|modelo" (da página) ou o dicionário gravado -> a escolha conferida."""
    if isinstance(valor, dict):
        motor, modelo = str(valor.get("motor", "")), str(valor.get("modelo", ""))
    else:
        motor, _, modelo = str(valor or "").partition("|")
    if motor not in (*ASSINATURAS, *API) or not modelo or len(modelo) > 100:
        raise ValueError("Modelo inválido.")
    return {"motor": motor, "modelo": modelo}


def nome(escolha: dict[str, str]) -> str:
    """Como a página mostra a escolha: "Haiku 4.5 · Claude (assinatura)"."""
    motor, modelo = escolha.get("motor", ""), escolha.get("modelo", "")
    if motor == "plano":
        rotulo = next((m["nome"] for m in modelos.CLAUDE if m["id"] == modelo), modelo)
        return f"{rotulo} · Claude (assinatura)"
    if motor == "codex":
        return f"{modelo} · Codex (assinatura)"
    rotulo = next((n for mid, n in API.get(motor, []) if mid == modelo), modelo)
    return f"{rotulo} · {NOMES_API.get(motor, motor)} (API)"


def rapido_nas_ligacoes(escolha: dict[str, str]) -> bool:
    return escolha.get("motor") in API


def criar(escolha: dict[str, str], pasta: Path) -> Any:
    """O motor da escolha; sem a chave da API, o padrão (Haiku pela assinatura)."""
    motor, modelo = escolha.get("motor", ""), escolha.get("modelo", "")
    if motor == "plano":
        return rapido.MotorPlano(modelo, pasta)
    if motor == "codex":
        return rapido.MotorCodex(modelo, pasta / "codex")
    if motor in API:
        via = {"motor": motor, "modelo": modelo, "endereco": "", "arquivo_chave": "",
               "raciocinio": "minimal", "max_tokens": MAX_TOKENS}  # fmt: skip
        if (feito := rapido.criar_motor(via, pasta)) is not None:
            return feito
    return rapido.MotorPlano(PADRAO["modelo"], pasta)


def chaves() -> list[dict[str, Any]]:
    """As chaves de API que o agente pode usar (as mesmas da via rápida), para a página."""
    saida = []
    for motor in API:
        situacao = rapido.situacao_da_chave(motor)
        saida.append(
            {
                "motor": motor,
                "nome": NOMES_API[motor],
                "tem": bool(situacao.get("tem")),
                "fim": situacao.get("fim", ""),
                "origem": situacao.get("origem", ""),
                "modelo": API[motor][0][0],
            }
        )
    return saida
