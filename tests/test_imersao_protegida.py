"""A Imersão é zona protegida no redesenho do painel (docs/plano-design.md): o Zé 3D, a abertura e
o jeito como ele se apresenta funcionam exatamente como estão.

Este teste guarda um resumo de cada arquivo dela e dos trechos do painel que a ligam (o item do
menu, a moldura, a tela cheia, o desligar) e falha se algo mudar sem querer, dizendo o quê. Mudou
de propósito (um PR da própria Imersão)? `ZE_ATUALIZAR_IMERSAO=1 uv run pytest
tests/test_imersao_protegida.py` regrava os resumos, e a mudança fica à vista no PR.
"""

import hashlib
import json
import os
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RESUMOS = Path(__file__).with_name("imersao_protegida.json")
# A Imersão inteira: o servidor dela, a página 3D e o módulo do painel que a abre.
INTEIROS = [
    RAIZ / "zervis" / "imersivo",
    RAIZ / "zervis" / "portal" / "imersao.py",
    RAIZ / "zervis" / "portal" / "web" / "modulos" / "imersao.js",
]
# Arquivos do painel que a ligam: só as linhas que falam dela (mover a linha de lugar não conta).
TRECHOS = [
    "zervis/portal/web/index.html",
    "zervis/portal/web/painel.css",
    "zervis/portal/web/modulos/navegacao.js",
    "zervis/portal/web/modulos/acoes.js",
    "zervis/portal/web/modulos/estado.js",
    "zervis/portal/web/modulos/principal.js",
    "zervis/portal/servidor.py",
]
DA_IMERSAO = re.compile(r"imers|holo|palco", re.IGNORECASE)


def _resumo(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()[:16]


def _arquivos() -> list[Path]:
    todos: list[Path] = []
    for caminho in INTEIROS:
        if caminho.is_file():
            todos.append(caminho)
        else:
            todos += [
                p for p in caminho.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
            ]  # fmt: skip
    return sorted(todos)


def resumos() -> dict[str, str]:
    atuais = {str(p.relative_to(RAIZ)): _resumo(p.read_bytes()) for p in _arquivos()}
    for nome in TRECHOS:
        linhas = (RAIZ / nome).read_text().splitlines()
        trecho = sorted(x.strip() for x in linhas if DA_IMERSAO.search(x))
        atuais[f"{nome} (trechos da Imersão)"] = _resumo("\n".join(trecho).encode())
    return atuais


def test_a_imersao_continua_como_esta() -> None:
    atuais = resumos()
    if os.environ.get("ZE_ATUALIZAR_IMERSAO") == "1":
        RESUMOS.write_text(json.dumps(atuais, indent=1, sort_keys=True) + "\n")
    guardados = json.loads(RESUMOS.read_text())
    mudaram = sorted(k for k in set(guardados) | set(atuais) if guardados.get(k) != atuais.get(k))
    assert not mudaram, (
        "A Imersão é zona protegida (docs/plano-design.md) e mudou: "
        + ", ".join(mudaram)
        + ". Se foi de propósito, ZE_ATUALIZAR_IMERSAO=1 regrava os resumos."
    )


def test_a_trava_enxerga_a_imersao_inteira() -> None:
    """Sem isto, um arquivo novo dela, fora da lista, passaria sem trava."""
    nomes = set(resumos())
    assert any(n.startswith("zervis/imersivo/web/") for n in nomes)
    assert "zervis/portal/web/modulos/imersao.js" in nomes
    assert len([n for n in nomes if n.startswith("zervis/imersivo/")]) >= 60
