"""Quando o Zé fala sozinho: o modo de fala (ADR 0018).

Três tipos de fala espontânea, separados:
- **notificação**: algo aconteceu, em uma frase ("A sessão Loja terminou.");
- **urgente**: alguém espera a pessoa (aprovação, créditos esgotados, erro);
- **resposta**: o que o agente da sessão respondeu, resumido para ouvir.

Três modos, trocados a qualquer hora (painel, atalho, voz):
- **Silencioso**: o Zé não fala; tudo fica na tela. Como ele ouve é outra escolha (ADR 0022).
- **Normal** (padrão; "avisos" na configuração): notificações, urgências e o resumo do resultado
  de cada sessão falados. Chamava-se "Avisos" até 13/10/2026.
- **Live** (era "Mãos livres" até 27/10/2026, ADR 0042): tudo falado, inclusive a resposta da
  sessão, resumida; com a voz conectada, a conversa é em tempo real, como numa ligação.

Avisos de sessões incluem o resultado mesmo com a sessão aberta, por decisão de 15/10/2026.
Silencioso continua só na tela. O modo fica em `<config>/fala.json`.
"""

import json
import re
from pathlib import Path
from typing import Literal

from zervis import lugares

ARQUIVO = lugares.CONFIG / "fala.json"
MODOS = ("silencioso", "avisos", "live")
NOMES = {"silencioso": "Silencioso", "avisos": "Normal", "live": "Live"}
ANTIGOS = {"maos_livres": "live"}  # o nome gravado antes de 27/10/2026 continua valendo
PADRAO = "avisos"
Tipo = Literal["notificacao", "urgente", "resposta"]


def ler(arquivo: Path = ARQUIVO) -> str:
    try:
        modo = json.loads(arquivo.read_text()).get("modo")
    except (OSError, ValueError, AttributeError):
        return PADRAO
    modo = ANTIGOS.get(modo, modo)
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
        return modo == "live"
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


MANCHETE_PALAVRAS = 30
REPETIR_S = 120.0  # o mesmo aviso não se repete antes disto (ADR 0027)


def manchete(texto: str, palavras: int = MANCHETE_PALAVRAS) -> str:
    """O aviso falado em no máximo `palavras` (ADR 0027): as frases inteiras que couberem e, se
    sobrar, "O resto está na tela." Texto curto passa como está."""
    if len(texto.split()) <= palavras:
        return texto
    saida: list[str] = []
    for frase in re.split(r"(?<=[.!?:;])\s+", texto.strip()):
        if len(" ".join([*saida, frase]).split()) > palavras:
            break
        saida.append(frase)
    if not saida:  # uma frase só, comprida: corta nas palavras
        saida = [" ".join(texto.split()[:palavras]).rstrip(",;:") + "…"]
    return f"{' '.join(saida)} O resto está na tela."
