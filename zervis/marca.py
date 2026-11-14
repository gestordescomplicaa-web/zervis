"""A marca de quem usa nos posts (ADR 0093): nome, @ do Instagram, logo, cores e fontes.

O site a declara no `zervis.json` (`marca`), e a paleta pode ser trocada em Marketing. Nada de uma
marca em particular fica no código: sem declaração, vale uma paleta neutra.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# A paleta de quem não declarou marca: neutra, escura, com um azul de destaque.
CORES_PADRAO = {
    "fundo": "#111114", "superficie": "#1b1b20", "texto": "#f4f4f6", "suave": "#a3a3ad",
    "destaque": "#4f8cff", "destaque2": "#8b5cf6",
}  # fmt: skip
COR = re.compile(r"#[0-9a-fA-F]{6}")
FONTE = re.compile(r"[A-Za-z0-9 ]{1,40}")
ARROBA = re.compile(r"[A-Za-z0-9._]{1,30}")


@dataclass(frozen=True)
class Marca:
    nome: str = ""
    instagram: str = ""
    logo: str = ""  # o caminho do logo no repositório do site
    cores: tuple[tuple[str, str], ...] = tuple(CORES_PADRAO.items())
    titulo: str = ""  # a fonte dos títulos (do Google Fonts); vazia, a do sistema
    texto: str = ""  # a fonte do texto

    def cor(self, nome: str) -> str:
        return dict(self.cores).get(nome, CORES_PADRAO[nome])


def cores_validas(cores: Any) -> dict[str, str]:
    """Só as cores conhecidas, em `#rrggbb`; o resto fica com o padrão."""
    if not isinstance(cores, dict):
        return {}
    return {k: str(v) for k, v in cores.items() if k in CORES_PADRAO and COR.fullmatch(str(v))}


def _fonte(valor: Any) -> str:
    texto = str(valor or "").strip()
    return texto if FONTE.fullmatch(texto) else ""


def _logo(valor: Any) -> str:
    texto = str(valor or "").strip().strip("/")
    if not texto or ".." in Path(texto).parts or str(valor).startswith("/"):
        return ""
    return texto


def ler_marca(texto: str) -> Marca | None:
    """A marca declarada no `zervis.json` (None se não houver ou estiver malformada)."""
    try:
        dados = json.loads(texto)
    except ValueError:
        return None
    marca = dados.get("marca") if isinstance(dados, dict) else None
    if not isinstance(marca, dict):
        return None
    fontes_cruas = marca.get("fontes")
    fontes: dict[str, Any] = fontes_cruas if isinstance(fontes_cruas, dict) else {}
    arroba = str(marca.get("instagram", "")).strip().lstrip("@")
    return Marca(
        nome=" ".join(str(marca.get("nome", "")).split())[:60],
        instagram=arroba if ARROBA.fullmatch(arroba) else "",
        logo=_logo(marca.get("logo")),
        cores=tuple({**CORES_PADRAO, **cores_validas(marca.get("cores"))}.items()),
        titulo=_fonte(fontes.get("titulo")),
        texto=_fonte(fontes.get("texto")),
    )
