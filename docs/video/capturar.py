"""Captura uma página de vídeo quadro a quadro, com vários Chromiums sem tela em paralelo (CDP).

Uso:
  capturar.py <pagina.html> <pasta> --tamanho 1080x1920 --duracao 24 [--trabalhadores 6] [--dados X]
  capturar.py <pagina.html> <pasta> --tamanho 1080x1920 --tempos 1.5,7.2   (quadros soltos, PNG)

A página define `window.render(t)` (cada quadro é função só do tempo) e `window.pronto` (as fontes,
as imagens e os dados carregados). `--dados` vira `?dados=<arquivo>` (o `narracao.js`). Cada
trabalhador pega um quadro a cada N, e os quadros saem em JPEG (`0000.jpg`...), que o FFmpeg lê.
"""

import argparse
import asyncio
import base64
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import websockets

FPS = 30
CHROMIUM = os.environ.get("CHROMIUM", "chromium")


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def trabalhador(
    url: str, largura: int, altura: int, quadros: list[tuple[Path, float]], fmt: str
) -> None:
    porta = porta_livre()
    perfil = tempfile.mkdtemp(prefix="video-chromium-")
    proc = subprocess.Popen(  # noqa: S603 (o Chromium do sistema, sem entrada de fora)
        [CHROMIUM, "--headless=new", f"--remote-debugging-port={porta}",
         f"--user-data-dir={perfil}", f"--window-size={largura},{altura}",
         "--hide-scrollbars", "--mute-audio",
         "--force-device-scale-factor=1", "--allow-file-access-from-files", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    try:
        alvos: list[dict[str, Any]] = []
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{porta}/json") as r:
                    alvos = json.load(r)
                break
            except OSError:
                await asyncio.sleep(0.1)
        ws_url = next(a["webSocketDebuggerUrl"] for a in alvos if a["type"] == "page")
        async with websockets.connect(ws_url, max_size=2**28) as ws:
            n = 0

            async def cdp(metodo: str, **params: object) -> dict[str, Any]:
                nonlocal n
                n += 1
                await ws.send(json.dumps({"id": n, "method": metodo, "params": params}))
                while True:
                    r = json.loads(await ws.recv())
                    if r.get("id") == n:
                        if "error" in r:
                            raise RuntimeError(r["error"])
                        return dict(r.get("result", {}))

            await cdp("Emulation.setDeviceMetricsOverride", width=largura, height=altura,
                      deviceScaleFactor=1, mobile=False)  # fmt: skip
            await cdp("Page.navigate", url=url)
            for _ in range(100):  # espera a página definir window.pronto
                r = await cdp("Runtime.evaluate", expression="typeof window.pronto")
                if r.get("result", {}).get("value") == "object":
                    break
                await asyncio.sleep(0.1)
            await cdp("Runtime.evaluate", expression="window.pronto", awaitPromise=True)
            opcoes: dict[str, Any] = {"format": fmt}
            if fmt == "jpeg":
                opcoes["quality"] = 92
            for arquivo, t in quadros:
                await cdp("Runtime.evaluate", expression=f"window.render({t})")
                r = await cdp("Page.captureScreenshot", **opcoes)
                arquivo.write_bytes(base64.b64decode(r["data"]))
    finally:
        proc.terminate()


async def principal(args: argparse.Namespace) -> None:
    largura, altura = (int(x) for x in args.tamanho.split("x"))
    url = Path(args.pagina).resolve().as_uri()
    if args.dados:
        url += "?dados=" + urllib.parse.quote(Path(args.dados).resolve().as_uri(), safe="")
    pasta = Path(args.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    if args.tempos:
        tempos = [float(x) for x in args.tempos.split(",")]
        quadros = [(pasta / f"{t:06.2f}.png", t) for t in tempos]
        await trabalhador(url, largura, altura, quadros, "png")
        return
    todos = [(pasta / f"{i:04d}.jpg", i / FPS) for i in range(round(args.duracao * FPS))]
    w = args.trabalhadores
    inicio = time.monotonic()
    await asyncio.gather(
        *(trabalhador(url, largura, altura, todos[k::w], "jpeg") for k in range(w))
    )
    gasto = time.monotonic() - inicio
    cada = gasto / len(todos)
    print(f"{len(todos)} quadros em {gasto:.0f}s ({cada:.2f}s por quadro, {w} em paralelo)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("pagina")
    p.add_argument("pasta")
    p.add_argument("--tamanho", default="1920x1080")
    p.add_argument("--duracao", type=float, default=0)
    p.add_argument("--trabalhadores", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    p.add_argument("--dados", default="")
    p.add_argument("--tempos", default="")
    asyncio.run(principal(p.parse_args()))
