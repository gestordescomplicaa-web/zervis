"""A lista da página Prospecção (ADR 0140): as empresas por ramo, numa linha cada.

A Prospecção cuida da primeira mensagem; a conversa depois é de quem usa, no WhatsApp. Por isso a
página mostra pouco de cada empresa (o nome, o número e o estado) e deixa as descartadas de fora:
elas ficam no banco para ninguém receber duas vezes, e na tela só contam.
"""

from typing import Any

from zervis.prospeccao import dono
from zervis.prospeccao.funil import ROTULOS

NA_TELA = 30  # por ramo, as mais recentes: o resto conta no total e se lê pela voz
POR_CNPJ = "Adicionadas pelo CNPJ"
OUTROS = "Outros"


def _titulo(ramo: str) -> str:
    return ramo[:1].upper() + ramo[1:]


def ramo_de(p: dict[str, Any], ramos: list[str]) -> str:
    """O grupo da empresa: o ramo da Configuração que a buscou. As de antes de 25/11/2026 não o
    guardaram: vale o ramo cujas palavras estão na categoria do Maps ("autopeças" em "Loja de
    autopeças") e, com um ramo só na Configuração, ele (foi o único a buscar)."""
    if p.get("origem") == "cnpj":
        return POR_CNPJ
    ramo = str(p.get("ramo") or "")
    if not ramo and p.get("origem") == "maps":
        categoria = dono.sem_acento(str((p.get("lugar") or {}).get("categoria", "")))

        def cabe(r: str) -> bool:
            palavras = [w for w in dono.sem_acento(r).split() if len(w) > 2]
            return bool(palavras) and all(w in categoria for w in palavras)

        ramo = next((r for r in ramos if cabe(r)), ramos[0] if len(ramos) == 1 else "")
    return _titulo(ramo) if ramo else OUTROS


def _linha(p: dict[str, Any]) -> dict[str, Any]:
    """O nome, o número (o que recebeu; antes do envio, o primeiro) e o estado."""
    numeros = [t["numero"] for t in p.get("telefones", [])]
    telefone = p.get("telefone_enviado") or next(iter(numeros), "")
    return {
        "id": p["id"], "nome": p["nome"], "status": p["status"],
        "rotulo": ROTULOS.get(p["status"], p["status"]),
        "telefone": telefone or str((p.get("lugar") or {}).get("telefone", "")),
        "resposta": p.get("resposta", ""), "erro": p.get("erro", ""),
    }  # fmt: skip


def grupos(ramos: list[str], todas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """As empresas por ramo, na ordem da Configuração, depois "Outros" e as do CNPJ. As que
    esperam aprovação têm o cartão delas. `todas`, da mais recente para a mais antiga."""
    por_ramo: dict[str, list[dict[str, Any]]] = {}
    for p in todas:
        if p.get("status") not in ("aprovar", "descartada"):
            por_ramo.setdefault(ramo_de(p, ramos), []).append(p)
    ordem = [_titulo(r) for r in ramos]

    def lugar(nome: str) -> int:
        if nome in ordem:
            return ordem.index(nome)
        return len(ordem) + (nome == OUTROS) + 2 * (nome == POR_CNPJ)

    resultado = []
    for nome in sorted(por_ramo, key=lugar):
        lista = por_ramo[nome]
        contagem: dict[str, int] = {}
        for p in lista:
            contagem[p["status"]] = contagem.get(p["status"], 0) + 1
        resultado.append(
            {
                "ramo": nome,
                "total": len(lista),
                "contagem": contagem,
                "empresas": [_linha(p) for p in lista[:NA_TELA]],
            }
        )
    return resultado
