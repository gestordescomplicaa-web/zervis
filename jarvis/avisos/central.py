"""A central de avisos (ADR 0029): o Zé narra o que as sessões fazem; nunca fala por elas.

O fim de uma tarefa vira "A sessão Loja terminou." e, em Mãos livres, uma frase em terceira
pessoa sobre o que ela fez ("Ela corrigiu o login e os testes passaram."), escrita por um modelo
pequeno a partir da resposta da sessão. Sem o modelo, a primeira frase da resposta, marcada como
citação ("Ela respondeu: …"), para quem ouve saber que não é o Zé falando.
"""

import re

from jarvis.avisos.modo import para_ouvir

SISTEMA = (
    "Você resume, para ser ouvida em voz alta, a resposta de um agente de código ao usuário. "
    "Responda só com a frase pedida, sem aspas."
)
PALAVRAS_MAX = 30


def pedido_de_resumo(resposta: str) -> str:
    return (
        "Em uma frase curta (até 20 palavras), em português, em terceira pessoa e começando por "
        '"Ela", conte o que o agente respondeu ou fez. Quem ouve é o usuário: trate-o por '
        '"você". Sem código, caminhos, links nem marcação.\n\nResposta do agente:\n'
        + resposta[:4000]
    )


def limpar_resumo(saida: str) -> str | None:
    """A frase do modelo, se servir: uma linha, curta, em terceira pessoa."""
    frase = " ".join(saida.split()).strip(" \"'“”")
    if not frase or len(frase.split()) > PALAVRAS_MAX or not frase.startswith("Ela"):
        return None
    return frase if frase.endswith((".", "!", "?")) else f"{frase}."


def primeira_frase(texto: str) -> str:
    limpo = para_ouvir(texto)
    return re.split(r"(?<=[.!?])\s+", limpo, maxsplit=1)[0] if limpo else ""


def narrar(nome: str, resumo: str | None, resposta: str) -> str:
    """O aviso de fim de tarefa em Mãos livres, sempre na voz de quem narra."""
    base = f"A sessão {nome} terminou."
    if resumo:
        return f"{base} {resumo}"
    if frase := primeira_frase(resposta):
        return f"{base} Ela respondeu: {frase}"
    return base
