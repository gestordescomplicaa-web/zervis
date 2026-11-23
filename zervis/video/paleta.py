"""A paleta dos vídeos a partir de um site (ADR 0117): quem usa cola um endereço e o Zé monta as
cores sozinho, olhando o site como ele aparece.

O print vem da captura da Imersão (só HTTPS, atrás da trava de rede, ADR 0058). Das cores do
print, reduzidas às principais e pesadas pela área: o fundo é a que mais ocupa; o texto, a de
mais contraste com ele; os destaques, as mais vivas que aparecem de verdade (um botão, um
título), a segunda com outro tom. O resto sai da mistura dessas. Nada vem do modelo.
"""

import colorsys
import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from zervis.imersivo import capturas
from zervis.marca import CORES_PADRAO

Rgb = tuple[int, int, int]


class PaletaErro(ValueError):
    """O site não abriu ou não deu para tirar cores; a mensagem vai para a tela."""


def _hex(c: Rgb) -> str:
    return "#{:02x}{:02x}{:02x}".format(*c)


def _rgb(texto: str) -> Rgb:
    t = texto.lstrip("#")
    return int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)


def luminancia(c: Rgb) -> float:
    def canal(v: int) -> float:
        x = v / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(v) for v in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: Rgb, b: Rgb) -> float:
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _mistura(a: Rgb, b: Rgb, k: float) -> Rgb:
    return (
        round(a[0] + (b[0] - a[0]) * k),
        round(a[1] + (b[1] - a[1]) * k),
        round(a[2] + (b[2] - a[2]) * k),
    )


def _hsv(c: Rgb) -> tuple[float, float, float]:
    return colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)


def _distancia_de_tom(a: Rgb, b: Rgb) -> float:
    d = abs(_hsv(a)[0] - _hsv(b)[0])
    return min(d, 1 - d)


def _girar(c: Rgb, graus: float) -> Rgb:
    h, s, v = _hsv(c)
    r, g, b = colorsys.hsv_to_rgb((h + graus / 360) % 1, s, v)
    return round(r * 255), round(g * 255), round(b * 255)


def principais(png: bytes, quantas: int = 16) -> list[tuple[float, Rgb]]:
    """As cores principais do print, com a parte da área de cada uma (de 0 a 1). As cores são as
    de verdade (sem média): as parecidas se juntam e vale a mais frequente do grupo, para que o
    roxo do botão saia o roxo exato da marca."""
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(png)) as imagem:
            pequena = imagem.convert("RGB").resize((320, 200), Image.Resampling.NEAREST)
    except (UnidentifiedImageError, OSError) as erro:
        raise PaletaErro("O print do site não abriu.") from erro
    contadas = sorted(pequena.getcolors(320 * 200) or [], reverse=True)
    grupos: list[list[Any]] = []  # [quantos, a cor do grupo]
    for n, cor in contadas:
        perto = next((g for g in grupos if _perto(g[1], cor)), None)
        if perto is not None:
            perto[0] += n
        else:
            grupos.append([n, tuple(cor)])
    total = sum(g[0] for g in grupos) or 1
    return sorted(((g[0] / total, g[1]) for g in grupos), reverse=True)[:quantas]


def _perto(a: Rgb, b: Rgb) -> bool:
    return sum((x - y) ** 2 for x, y in zip(a, b, strict=True)) < 24**2


def extrair(png: bytes) -> dict[str, str]:
    """A paleta (as chaves de `CORES_PADRAO`) a partir do print de um site."""
    cores = principais(png)
    if not cores:
        raise PaletaErro("O site não tem cores para tirar.")
    fundo = cores[0][1]
    # o texto: a cor (com alguma presença) de mais contraste com o fundo; se nenhuma lê bem, o
    # preto ou o branco quase puros
    candidatos = [c for parte, c in cores if parte >= 0.003]
    texto = max(candidatos, key=lambda c: contraste(c, fundo))
    if contraste(texto, fundo) < 7:
        texto = (17, 17, 20) if luminancia(fundo) > 0.4 else (245, 245, 247)
    # os destaques: as cores vivas que aparecem de verdade, pela área vezes a saturação
    vivas = [
        (parte * _hsv(c)[1], c)
        for parte, c in cores
        if parte >= 0.0015
        and _hsv(c)[1] >= 0.35
        and _hsv(c)[2] >= 0.3
        and contraste(c, fundo) >= 1.6
        and contraste(c, texto) >= 1.4  # um destaque não é a cor do texto
    ]
    vivas.sort(reverse=True)
    destaque = vivas[0][1] if vivas else _rgb(CORES_PADRAO["destaque"])
    outro = next(
        (
            c
            for _, c in vivas[1:]
            if _distancia_de_tom(c, destaque) >= 0.07 and _hsv(c)[1] >= 0.45 and _hsv(c)[2] >= 0.5
        ),
        None,
    )
    destaque2 = outro or _girar(destaque, 32)
    return {
        "fundo": _hex(fundo),
        "superficie": _hex(_mistura(fundo, texto, 0.06)),
        "texto": _hex(texto),
        "suave": _hex(_mistura(texto, fundo, 0.45)),
        "destaque": _hex(destaque),
        "destaque2": _hex(destaque2),
    }


def tinta_e_papel(cores: dict[str, str]) -> dict[str, str]:
    """A cor escura e a clara da paleta, seja ela de fundo escuro ou claro: o estilo claro
    (Editorial) escreve com a tinta sobre o papel, sem depender de qual é o fundo do site."""
    a, b = _rgb(cores["fundo"]), _rgb(cores["texto"])
    escura, clara = sorted((a, b), key=luminancia)
    return {"tinta": _hex(escura), "papel": _hex(_mistura(clara, (255, 255, 255), 0.35))}


def do_site(
    url: str, pasta: Path, capturar: Callable[[str, Path], dict[str, Any]] = capturas.capturar
) -> dict[str, str]:
    """Abre o site (só HTTPS, atrás da trava) e tira a paleta do print."""
    endereco = url.strip()
    if not endereco.lower().startswith(("http://", "https://")):
        endereco = f"https://{endereco}"
    endereco = "https://" + endereco.split("://", 1)[1]
    try:
        registro = capturar(endereco, pasta)
        png = (pasta / str(registro["arquivo"])).read_bytes()
    except capturas.CapturaErro as erro:
        raise PaletaErro(f"O site não abriu: {erro}.") from erro
    except (OSError, KeyError) as erro:
        raise PaletaErro("O site não abriu.") from erro
    return extrair(png)


def ler(arquivo: Path) -> dict[str, Any]:
    """A paleta escolhida: {"origem": "marca"} ou {"origem": "site", "url", "cores"}."""
    try:
        dados = json.loads(arquivo.read_text())
    except (OSError, ValueError):
        return {"origem": "marca"}
    if not isinstance(dados, dict) or dados.get("origem") != "site":
        return {"origem": "marca"}
    cores: dict[str, Any] = dados["cores"] if isinstance(dados.get("cores"), dict) else {}
    validas = {k: str(v) for k, v in cores.items() if k in CORES_PADRAO and _valida(str(v))}
    if len(validas) < len(CORES_PADRAO):
        return {"origem": "marca"}
    return {"origem": "site", "url": str(dados.get("url", ""))[:200], "cores": validas}


def _valida(cor: str) -> bool:
    return (
        len(cor) == 7
        and cor.startswith("#")
        and all(c in "0123456789abcdefABCDEF" for c in cor[1:])
    )
