"""Os estilos dos vídeos (ADR 0106): cada um é uma pasta com o visual e, se quiser, cenas próprias.

    estilo.json   {"nome", "descricao", "fontes": {"titulo", "texto", "legenda"}, "onda",
                  "trilha": {"bpm", "energia"}, "tom",
                  "cenas": {"<tipo novo>": "<o formato, para o modelo>"}}
    estilo.css    o visual, por cima da estrutura (`web/base.css`); as cores vêm da marca
    cenas.js      (opcional) cenas novas ou trocadas: `Ze.cena(tipo, {montar, render})`

O Zé traz o "zervis" (`zervis/video/estilos/`). Os de quem usa ficam em
`<config>/video/estilos/<pasta>/` e valem do mesmo jeito; com o mesmo nome de pasta, o de quem usa
vale no lugar do embutido. Nada de um estilo prende o Zé: apagar a pasta volta ao padrão.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from zervis import lugares

log = logging.getLogger(__name__)
EMBUTIDOS = Path(__file__).parent / "estilos"
DE_QUEM_USA = lugares.CONFIG / "video" / "estilos"
PADRAO = "zervis"
ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
FONTE = re.compile(r"[A-Za-z0-9 ]{1,40}")
TIPO = re.compile(r"[a-z][a-z0-9_]{1,30}")
ENERGIAS = ("calma", "media", "alta")


@dataclass(frozen=True)
class Estilo:
    id: str
    nome: str
    pasta: Path
    descricao: str = ""
    fonte_titulo: str = ""
    fonte_texto: str = ""
    fonte_legenda: str = ""  # a da legenda, se o estilo quiser outra (regular e itálica)
    onda: bool = True
    bpm: int = 120
    energia: str = "media"
    tom: str = ""
    cenas_extras: dict[str, str] = field(default_factory=dict)  # tipo -> o formato, para o modelo
    proprio: bool = False  # de quem usa (em <config>), não embutido

    @property
    def css(self) -> Path | None:
        arquivo = self.pasta / "estilo.css"
        return arquivo if arquivo.is_file() else None

    @property
    def js(self) -> Path | None:
        arquivo = self.pasta / "cenas.js"
        return arquivo if arquivo.is_file() else None

    def fontes_url(self, titulo: str = "", texto: str = "") -> str:
        """O endereço do Google Fonts das fontes deste vídeo (as da marca valem antes)."""
        familias = dict.fromkeys(
            f for f in (titulo or self.fonte_titulo, texto or self.fonte_texto) if f
        )
        if not familias:
            return ""
        partes = "&".join(f"family={quote_plus(f)}:wght@400;600;700;800" for f in familias)
        if self.fonte_legenda and self.fonte_legenda not in familias:
            partes += f"&family={quote_plus(self.fonte_legenda)}:ital@0;1"
        return f"https://fonts.googleapis.com/css2?{partes}&display=block"

    def para_tela(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "nome": self.nome,
            "descricao": self.descricao,
            "proprio": self.proprio,
        }


def _ler(pasta: Path, proprio: bool) -> Estilo | None:
    try:
        dados = json.loads((pasta / "estilo.json").read_text())
    except (OSError, ValueError) as erro:
        log.warning("vídeo: estilo %s ilegível (%s)", pasta.name, erro)
        return None
    if not isinstance(dados, dict) or not ID.fullmatch(pasta.name):
        return None
    fontes: dict[str, Any] = dados["fontes"] if isinstance(dados.get("fontes"), dict) else {}
    trilha: dict[str, Any] = dados["trilha"] if isinstance(dados.get("trilha"), dict) else {}

    def fonte(nome: str) -> str:
        valor = str(fontes.get(nome, ""))
        return valor if FONTE.fullmatch(valor) else ""

    try:
        bpm = min(160, max(70, int(trilha.get("bpm", 120))))
    except (TypeError, ValueError):
        bpm = 120
    extras: dict[str, Any] = dados["cenas"] if isinstance(dados.get("cenas"), dict) else {}
    return Estilo(
        id=pasta.name,
        nome=str(dados.get("nome") or pasta.name)[:40],
        pasta=pasta,
        descricao=str(dados.get("descricao", ""))[:160],
        fonte_titulo=fonte("titulo"),
        fonte_texto=fonte("texto"),
        fonte_legenda=fonte("legenda"),
        onda=dados.get("onda") is not False,
        bpm=bpm,
        energia=str(trilha.get("energia")) if trilha.get("energia") in ENERGIAS else "media",
        tom=str(dados.get("tom", ""))[:300],
        cenas_extras={
            str(k): str(v)[:400] for k, v in extras.items() if TIPO.fullmatch(str(k)) and v
        },
        proprio=proprio,
    )


def listar(embutidos: Path = EMBUTIDOS, proprios: Path = DE_QUEM_USA) -> list[Estilo]:
    """Os embutidos e os de quem usa; um de quem usa com o mesmo id vale no lugar."""
    achados: dict[str, Estilo] = {}
    for raiz, proprio in ((embutidos, False), (proprios, True)):
        if not raiz.is_dir():
            continue
        for pasta in sorted(p for p in raiz.iterdir() if p.is_dir()):
            if (estilo := _ler(pasta, proprio)) is not None:
                achados[estilo.id] = estilo
    return sorted(achados.values(), key=lambda e: (e.id != PADRAO, e.nome.lower()))


def achar(ident: str, embutidos: Path = EMBUTIDOS, proprios: Path = DE_QUEM_USA) -> Estilo:
    """O estilo pedido; sem ele (apagado, nome errado), o padrão."""
    todos = {e.id: e for e in listar(embutidos, proprios)}
    estilo = todos.get(ident) or todos.get(PADRAO)
    if estilo is None:
        raise FileNotFoundError("Nenhum estilo de vídeo encontrado.")
    return estilo
