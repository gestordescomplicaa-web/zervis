"""A biblioteca de ícones dos vídeos (ADR 0110): a Lucide inteira, 1.539 ícones de traço (ISC).

O diretor escreve o objeto que a fala diz, em inglês, como pensar ("pizza", "stethoscope",
"delivery truck"); `achar` devolve o ícone: o nome exato, ou o mais parecido pelas partes do nome
e pelas etiquetas que a Lucide publica, ou "sparkles" se nada combinar. O pedido ao modelo não
leva a lista inteira (seriam uns 5 mil tokens a mais por vídeo): a busca é aqui.

O desenho vem sempre do arquivo (`icones/lucide.json`, gerado do `lucide-static` 0.460.0, só com
as formas de traço), nunca do modelo.
"""

import json
import re
from functools import cache
from pathlib import Path

ARQUIVO = Path(__file__).parent / "icones" / "lucide.json"
RESERVA = "sparkles"


@cache
def _dados() -> dict[str, dict[str, object]]:
    bruto = json.loads(ARQUIVO.read_text())
    return {"icones": dict(bruto["icones"]), "tags": dict(bruto.get("tags") or {})}


def todos() -> dict[str, str]:
    """O miolo do SVG de cada ícone, pelo nome."""
    icones: dict[str, str] = _dados()["icones"]  # type: ignore[assignment]
    return icones


# Palavras comuns em vídeos de negócio que a Lucide não tem com esse nome.
SINONIMOS = {
    "invoice": "receipt",
    "bill": "receipt",
    "money": "banknote",
    "cash": "banknote",
    "payment": "credit card",
    "whatsapp": "message circle",
    "chat": "message circle",
    "burger": "sandwich",
    "hamburger": "sandwich",
    "restaurant": "utensils",
    "food": "utensils",
    "haircut": "scissors",
    "barber": "scissors",
    "salon": "scissors",
    "dentist": "smile",
    "tooth": "smile",
    "doctor": "stethoscope",
    "clinic": "hospital",
    "lawyer": "scale",
    "law": "scale",
    "legal": "scale",
    "home": "house",
    "estate": "house",
    "customer": "user",
    "client": "user",
    "team": "users",
    "employee": "user",
    "sale": "trending up",
    "sales": "trending up",
    "profit": "trending up",
    "time": "clock",
    "ai": "bot",
    "agent": "bot",
    "robot": "bot",
    "email": "mail",
    "spreadsheet": "file spreadsheet",
    "report": "chart column",
    "delivery": "truck",
    "motorcycle": "bike",
    "motorbike": "bike",
    "moped": "bike",
    "scooter": "bike",
    "courier": "bike",
    "warehouse": "warehouse",
    "stock": "package",
    "inventory": "package",
}


def _palavras(texto: str) -> list[str]:
    return [p for p in re.split(r"[^a-z0-9]+", texto.lower()) if p]


def _raiz(palavra: str) -> str:
    """O singular simples ("trucks" → "truck"), para comparar."""
    return (
        palavra[:-1]
        if len(palavra) > 3 and palavra.endswith("s") and not palavra.endswith("ss")
        else palavra
    )


@cache
def _indice() -> dict[str, tuple[frozenset[str], frozenset[str]]]:
    """Por ícone: as palavras do nome e as das etiquetas."""
    tags: dict[str, list[str]] = _dados()["tags"]  # type: ignore[assignment]
    return {
        nome: (
            frozenset(_raiz(p) for p in _palavras(nome)),
            frozenset(_raiz(p) for t in tags.get(nome, []) for p in _palavras(str(t))),
        )
        for nome in todos()
    }


@cache
def achar(pedido: str) -> str:
    """O ícone para o objeto pedido: exato, o mais parecido, ou a reserva."""
    nome = "-".join(_palavras(SINONIMOS.get(pedido.strip().lower(), pedido)))
    if nome in todos():
        return nome
    pedidas = [_raiz(w) for p in _palavras(pedido) for w in _palavras(SINONIMOS.get(p, p))]
    if not pedidas:
        return RESERVA
    melhor, nota_melhor = RESERVA, 0.0
    for icone, (do_nome, das_tags) in _indice().items():
        nota = 0.0
        for p in pedidas:
            if p in do_nome:
                nota += 3
            elif p in das_tags:
                nota += 2
            elif len(p) >= 4 and any(
                n.startswith(p) or p.startswith(n) for n in do_nome if len(n) >= 4
            ):
                nota += 1
        # o ícone "base" ganha das variações ("house" e não "map-pin-house")
        nota -= 0.5 * len(do_nome - set(pedidas)) + len(icone) / 1000
        if nota > nota_melhor:
            melhor, nota_melhor = icone, nota
    return melhor if nota_melhor >= 1 else RESERVA
