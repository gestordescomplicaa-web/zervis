"""Captura uma página de vídeo de `docs/video`, quadro a quadro, com vários Chromiums em paralelo.

Uso:
  capturar.py <pagina.html> <pasta> --tamanho 1080x1920 --duracao 23 [--trabalhadores 6] [--dados X]
  capturar.py <pagina.html> <pasta> --tamanho 1080x1920 --tempos 1.5,7.2   (quadros soltos, PNG)

Usa `zervis.video.captura` (o mesmo da função de Marketing). A página define `window.render(t)` e
`window.pronto`; `--dados` vira `?dados=<arquivo>`.
"""

import argparse
import time
import urllib.parse
from pathlib import Path

from zervis.video import captura

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("pagina")
    p.add_argument("pasta")
    p.add_argument("--tamanho", default="1920x1080")
    p.add_argument("--duracao", type=float, default=0)
    p.add_argument("--trabalhadores", type=int, default=0)
    p.add_argument("--dados", default="")
    p.add_argument("--tempos", default="")
    a = p.parse_args()
    largura, altura = (int(x) for x in a.tamanho.split("x"))
    url = Path(a.pagina).resolve().as_uri()
    if a.dados:
        url += "?dados=" + urllib.parse.quote(Path(a.dados).resolve().as_uri(), safe="")
    tempos = [float(x) for x in a.tempos.split(",")] if a.tempos else None
    inicio = time.monotonic()
    feitos = captura.capturar(
        url, Path(a.pasta), largura, altura, a.duracao, tempos, a.trabalhadores
    )
    print(f"{len(feitos)} quadros em {time.monotonic() - inicio:.0f}s")
