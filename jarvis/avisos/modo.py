"""Quando o Zé fala sozinho: o modo de fala (ADR 0018).

Três tipos de fala espontânea, separados:
- **notificação**: algo aconteceu, em uma frase ("A sessão Loja terminou.");
- **urgente**: alguém espera a pessoa (aprovação, créditos esgotados, erro);
- **resposta**: o que o agente da sessão respondeu, resumido para ouvir.

Três modos, trocados a qualquer hora (painel, atalho, voz):
- **Silencioso**: o Zé não fala; tudo fica na tela. Como ele ouve é outra escolha (ADR 0022).
- **Avisos** (padrão): notificações e urgências faladas; a resposta, só se a pessoa pedir.
- **Mãos livres**: tudo falado, inclusive a resposta da sessão, resumida.

Em qualquer modo, o que a pessoa já está vendo (a sessão aberta no painel) não é falado. O modo
fica em `<config>/fala.json`.
"""

import json
import re
from pathlib import Path
from typing import Literal

from jarvis import lugares

ARQUIVO = lugares.CONFIG / "fala.json"
MODOS = ("silencioso", "avisos", "maos_livres")
NOMES = {"silencioso": "Silencioso", "avisos": "Avisos", "maos_livres": "Mãos livres"}
PADRAO = "avisos"
Tipo = Literal["notificacao", "urgente", "resposta"]


def ler(arquivo: Path = ARQUIVO) -> str:
    try:
        modo = json.loads(arquivo.read_text()).get("modo")
    except (OSError, ValueError, AttributeError):
        return PADRAO
    return modo if modo in MODOS else PADRAO


def gravar(modo: str, arquivo: Path = ARQUIVO) -> str:
    if modo not in MODOS:
        raise ValueError("modo de fala desconhecido")
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".next")
    temporario.write_text(json.dumps({"modo": modo}))
    temporario.replace(arquivo)
    return modo


def falar(modo: str, tipo: Tipo, vendo: bool = False) -> bool:
    """Se o Zé fala isto agora. `vendo`: a pessoa já está com aquilo na tela."""
    if modo == "silencioso" or vendo:
        return False
    if tipo == "resposta":
        return modo == "maos_livres"
    return True


_CODIGO = re.compile(r"```.*?(```|$)", re.S)
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_URL = re.compile(r"https?://\S+")
_CAMINHO = re.compile(r"(?<!\w)(?:~|\.{0,2})?/[\w.@~/-]+|\b[\w-]+(?:/[\w.-]+)+")
_MARCAS = re.compile(r"[`*#>|]+|(?<!\w)_+|_+(?!\w)")


def para_ouvir(texto: str, limite: int = 320) -> str:
    """A resposta do agente pronta para ser ouvida: sem código, links nem marcação, e os caminhos
    só com o nome do arquivo; as primeiras frases, até `limite` caracteres."""
    texto = _CODIGO.sub(" ", texto)
    texto = _LINK.sub(r"\1", texto)
    texto = _URL.sub(" ", texto)
    texto = _CAMINHO.sub(lambda m: m.group(0).rstrip("/").rsplit("/", 1)[-1], texto)
    texto = _MARCAS.sub("", texto)
    linhas = [ln.strip(" -•\t") for ln in texto.splitlines()]
    texto = " ".join(ln if ln.endswith((".", "!", "?", ":")) else f"{ln}." for ln in linhas if ln)
    texto = re.sub(r"\s+", " ", texto).replace(" .", ".").strip()
    if len(texto) <= limite:
        return texto
    frases = re.split(r"(?<=[.!?])\s+", texto)
    saida = ""
    for frase in frases:
        if len(saida) + len(frase) + 1 > limite:
            break
        saida = f"{saida} {frase}".strip()
    return saida or texto[:limite].rsplit(" ", 1)[0] + "…"
