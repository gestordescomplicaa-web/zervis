"""Gera os ícones do celular a partir do logo do Zé (`.github/ze-logo.svg`), o mesmo do painel.

    uv run python android/icones.py

Saem o ícone adaptável do Zé Voz (a frente com o macaco e o brilho, o fundo é um degradê em XML,
e a versão de uma cor para os ícones temáticos do Android 13+), o ícone das notificações (vetor,
branco) e os ícones do painel instalado no celular (o manifesto). Precisa do `rsvg-convert`
(librsvg) e do `magick` (ImageMagick); rode de novo só quando o logo mudar.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOGO = RAIZ / ".github" / "ze-logo.svg"
RES = RAIZ / "android" / "app" / "src" / "main" / "res"
ICONES_PAINEL = RAIZ / "zervis" / "portal" / "web" / "icones"

# O macaco no logo (960 x 960): a caixa da tinta, sem o brilho, medida no próprio desenho.
CENTRO = (480.0, 476.0)
LARGURA = 742.0

# Ícone adaptável: camadas de 108 dp; o círculo de 66 dp no meio nunca é cortado pela máscara.
FRENTE_DP = 54.0  # a largura do macaco
XXXHDPI = 4  # px por dp; o Android reduz para as outras densidades
# Notificação: 24 dp, o macaco com ~22 dp de largura.
JANELA_NOTIFICACAO = 800.0
# Manifesto "maskable": o que importa fica no círculo de 80% do ícone.
MASCARAVEL = 0.6


def _partes(svg: str) -> tuple[str, list[tuple[str, str, str]]]:
    """As definições (degradês, brilho) e cada caminho do macaco: (d, x, y) do `translate`."""
    defs = re.search(r"<defs>.*?</defs>", svg, re.S)
    caminhos = re.findall(
        r'<path d="([^"]+)" fill="url\(#tinta\)" transform="translate\(([-\d.]+),([-\d.]+)\)"/>',
        svg,
    )
    if not defs or len(caminhos) < 5:
        sys.exit("O logo mudou de forma: confira os caminhos em .github/ze-logo.svg.")
    return defs.group(0), caminhos


def _tinta(caminhos: list[tuple[str, str, str]], cor: str) -> str:
    return "".join(
        f'<path d="{d}" fill="{cor}" transform="translate({x},{y})"/>' for d, x, y in caminhos
    )


def _svg(lado: float, corpo: str, defs: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {lado:g} {lado:g}">{defs}{corpo}'
        "</svg>"
    )


def _no_meio(lado: float, largura: float, corpo: str) -> str:
    """O macaco centrado num quadro de `lado`, com `largura` de lado a lado."""
    k = largura / LARGURA
    cx, cy = CENTRO
    meio = f"translate({lado / 2:g},{lado / 2:g}) scale({k:.6f}) translate({-cx:g},{-cy:g})"
    return f'<g transform="{meio}">{corpo}</g>'


def _render(svg: str, px: int, destino: Path) -> None:
    with tempfile.TemporaryDirectory() as pasta:
        fonte, png = Path(pasta) / "i.svg", Path(pasta) / "i.png"
        fonte.write_text(svg)
        desenhar = ["rsvg-convert", "-w", str(px), "-h", str(px), str(fonte), "-o", str(png)]
        subprocess.run(desenhar, check=True)  # noqa: S603
        destino.parent.mkdir(parents=True, exist_ok=True)
        webp = [
            "magick",
            str(png),
            "-define",
            "webp:lossless=true",
            "-quality",
            "100",
            str(destino),
        ]
        subprocess.run(webp, check=True)  # noqa: S603


def _notificacao(caminhos: list[tuple[str, str, str]]) -> str:
    """O ícone da barra de status: vetor branco (o Android pinta pela transparência)."""
    lado = JANELA_NOTIFICACAO
    cx, cy = CENTRO
    dx, dy = lado / 2 - cx, lado / 2 - cy
    grupos = "".join(
        f'        <group android:translateX="{x}" android:translateY="{y}">\n'
        f'            <path android:fillColor="#FFFFFFFF" android:pathData="{d}" />\n'
        "        </group>\n"
        for d, x, y in caminhos
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<!-- O ícone da notificação: o macaco do Zé, o mesmo do painel.\n"
        "     Gerado por android/icones.py. -->\n"
        '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
        '    android:width="24dp"\n'
        '    android:height="24dp"\n'
        f'    android:viewportWidth="{lado:g}"\n'
        f'    android:viewportHeight="{lado:g}">\n'
        f'    <group android:translateX="{dx:g}" android:translateY="{dy:g}">\n'
        f"{grupos}"
        "    </group>\n"
        "</vector>\n"
    )


def main() -> None:
    svg = LOGO.read_text()
    defs, caminhos = _partes(svg)
    brilho = f'<g filter="url(#brilho)">{_tinta(caminhos, "url(#tinta)")}</g>'
    camada = 108 * XXXHDPI
    mipmap = RES / "mipmap-xxxhdpi"
    _render(
        _svg(108, _no_meio(108, FRENTE_DP, brilho), defs),
        camada,
        mipmap / "ic_launcher_frente.webp",
    )
    _render(
        _svg(108, _no_meio(108, FRENTE_DP, _tinta(caminhos, "#fff"))),
        camada,
        mipmap / "ic_launcher_mono.webp",
    )
    (RES / "drawable" / "ic_ze.xml").write_text(_notificacao(caminhos))
    # O painel instalado no celular: o ícone como no painel, e um de borda a borda para a máscara.
    for px in (192, 512):
        _render(svg, px, ICONES_PAINEL / f"ze-{px}.webp")
    fundo = re.search(r"<rect [^>]*/>", svg)
    if not fundo:
        sys.exit("O logo mudou de forma: falta o fundo em .github/ze-logo.svg.")
    cheio = fundo.group(0).replace(
        'x="20" y="20" width="920" height="920" rx="190"', 'width="960" height="960"'
    )
    _render(
        _svg(960, cheio + _no_meio(960, 960 * MASCARAVEL, brilho), defs),
        512,
        ICONES_PAINEL / "ze-mascara-512.webp",
    )
    print("Ícones gerados.")


if __name__ == "__main__":
    main()
