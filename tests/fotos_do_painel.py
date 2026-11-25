"""Fotos do painel para comparar antes e depois de uma mudança visual (docs/plano-design.md).

    uv run python -m tests.fotos_do_painel <pasta>                # fotografa
    uv run python -m tests.fotos_do_painel --comparar <antes> <depois>

Cada página do menu (e as abertas sob demanda) no computador (1440 px) e no celular (390 px),
inteira, com as respostas de exemplo dos testes (`painel_respostas.json`, sem dados de ninguém)
e sem animação, para a mesma tela dar a mesma foto. Comparar lista as páginas que mudaram e
grava, em `<depois>/diferencas/`, a foto com o que mudou em vermelho. A Imersão é outro servidor
e fica de fora (ela tem os próprios testes e a trava `test_imersao_protegida.py`).
"""

import asyncio
import base64
import sys
import tempfile
from pathlib import Path

import websockets
from PIL import Image, ImageChops

from tests.test_painel_no_navegador import _carregar, _Navegador, _paginas, _painel

TAMANHOS = {"": (1440, 900), "-celular": (390, 844)}
ALTURA_MAXIMA = 6000
# Até isto, é ruído do desenho (a borda de um botão meio pixel para o lado), não mudança.
RUIDO = 40
PARADO = (
    "const s = document.createElement('style'); s.textContent = '*, *::before, *::after {"
    " animation: none !important; transition: none !important; caret-color: transparent"
    " !important; }'; document.head.append(s);"
)


async def _fotografar(depuracao: str, endereco: str, pasta: Path) -> list[Path]:
    fotos: list[Path] = []
    async with websockets.connect(depuracao, max_size=None) as ws:
        nav = _Navegador(ws)
        for sufixo, (largura, altura) in TAMANHOS.items():
            metricas = {"width": largura, "height": altura, "deviceScaleFactor": 1}
            metricas["mobile"] = largura < 600
            await nav.comando("Emulation.setDeviceMetricsOverride", metricas)
            await _carregar(nav, endereco)
            await nav.avaliar(PARADO)
            for pagina in _paginas():
                await nav.avaliar(
                    f'(async () => {{ location.hash = "#{pagina}"; await abrir(); }})()'
                )
                await asyncio.sleep(0.6)
                # A página inteira: o conteúdo rola dentro do painel, então a tela cresce até ele.
                cheia = await nav.avaliar(
                    "Math.max(innerHeight, (document.querySelector('#conteudo')?.scrollHeight"
                    " || 0) + (document.querySelector('#conteudo')?.getBoundingClientRect().top"
                    " || 0))"
                )
                alta = min(ALTURA_MAXIMA, max(altura, int(cheia or altura)))
                await nav.comando(
                    "Emulation.setDeviceMetricsOverride", {**metricas, "height": alta}
                )
                await asyncio.sleep(0.3)
                foto = await nav.comando("Page.captureScreenshot", {"format": "png"})
                destino = pasta / f"{pagina}{sufixo}.png"
                destino.write_bytes(base64.b64decode(foto["data"]))
                fotos.append(destino)
                await nav.comando("Emulation.setDeviceMetricsOverride", metricas)
    return fotos


def fotografar(pasta: Path) -> list[Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    with (
        tempfile.TemporaryDirectory() as temporaria,
        _painel(Path(temporaria)) as (depuracao, endereco),
    ):
        return asyncio.run(_fotografar(depuracao, endereco, pasta))


def comparar(antes: Path, depois: Path) -> dict[str, int]:
    """Quantos pixels mudaram em cada foto (-1: a página só existe num dos lados)."""
    resultado: dict[str, int] = {}
    saida = depois / "diferencas"
    nomes = {p.name for p in antes.glob("*.png")} | {p.name for p in depois.glob("*.png")}
    for nome in sorted(nomes):
        a, b = antes / nome, depois / nome
        if not a.exists() or not b.exists():
            resultado[nome] = -1
            continue
        imagem_a, imagem_b = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
        if imagem_a.size != imagem_b.size:
            largura = max(imagem_a.width, imagem_b.width)
            altura = max(imagem_a.height, imagem_b.height)
            imagem_a = _no_tamanho(imagem_a, largura, altura)
            imagem_b = _no_tamanho(imagem_b, largura, altura)
        diferenca = ImageChops.difference(imagem_a, imagem_b).convert("L")
        mascara = diferenca.point(lambda v: 255 if v > 8 else 0)
        pixels = mascara.width * mascara.height - mascara.histogram()[0]
        resultado[nome] = pixels
        if pixels:
            saida.mkdir(exist_ok=True)
            vermelho = Image.new("RGB", imagem_b.size, (255, 40, 40))
            Image.composite(vermelho, imagem_b, mascara).save(saida / nome)
    return resultado


def _no_tamanho(imagem: Image.Image, largura: int, altura: int) -> Image.Image:
    tela = Image.new("RGB", (largura, altura))
    tela.paste(imagem)
    return tela


def main(argumentos: list[str]) -> None:
    if len(argumentos) == 3 and argumentos[0] == "--comparar":
        resultado = comparar(Path(argumentos[1]), Path(argumentos[2]))
        mudaram = {n: p for n, p in resultado.items() if p < 0 or p > RUIDO}
        for nome, pixels in mudaram.items():
            print(f"{nome}: {'só num dos lados' if pixels < 0 else f'{pixels} pixels mudaram'}")
        print(f"{len(resultado) - len(mudaram)} iguais, {len(mudaram)} diferentes.")
        return
    if len(argumentos) == 1:
        fotos = fotografar(Path(argumentos[0]))
        print(f"{len(fotos)} fotos em {argumentos[0]}.")
        return
    sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
