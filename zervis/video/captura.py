"""Os quadros de um vídeo (ADR 0106): a página desenhada no Chromium sem tela, vários de uma vez.

Cada Chromium abre a página (`window.render(t)` e `window.pronto`) e fotografa um quadro a cada N,
pelo protocolo de depuração (CDP) num WebSocket local. O desfoque de fundo (`backdrop-filter`)
fica de fora das páginas de vídeo: no Chromium sem GPU, ele levava 2 s por quadro.
"""

import asyncio
import base64
import json
import logging
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import websockets

log = logging.getLogger(__name__)
FPS = 30
NAVEGADORES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
PAGINA = Path(__file__).parent / "web" / "pagina.html"


class CapturaErro(RuntimeError):
    """A página não desenhou; a mensagem vai para a tela."""


def navegador() -> str | None:
    return os.environ.get("CHROMIUM") or next(
        (b for b in map(shutil.which, NAVEGADORES) if b), None
    )


def trabalhadores_padrao() -> int:
    return max(1, min(6, (os.cpu_count() or 2) // 2))


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _alvos(porta: int) -> list[dict[str, Any]]:
    with urllib.request.urlopen(f"http://127.0.0.1:{porta}/json", timeout=2) as r:
        return list(json.load(r))


async def _trabalhador(
    binario: str,
    url: str,
    largura: int,
    altura: int,
    quadros: list[tuple[Path, float]],
    formato: str,
    feito: Callable[[], None],
) -> None:
    porta = _porta_livre()
    # Os processos filhos do Chromium ainda escrevem no perfil logo depois de ele fechar.
    with tempfile.TemporaryDirectory(prefix="ze-video-", ignore_cleanup_errors=True) as perfil:
        proc = await asyncio.create_subprocess_exec(
            binario, "--headless=new", f"--remote-debugging-port={porta}",
            f"--user-data-dir={perfil}", f"--window-size={largura},{altura}",
            "--hide-scrollbars", "--mute-audio", "--no-first-run", "--disable-extensions",
            "--force-device-scale-factor=1", "--allow-file-access-from-files", "about:blank",
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )  # fmt: skip
        try:
            alvos: list[dict[str, Any]] = []
            for _ in range(150):
                try:
                    alvos = await asyncio.to_thread(_alvos, porta)
                    break
                except OSError:
                    await asyncio.sleep(0.1)
            ws_url = next((a["webSocketDebuggerUrl"] for a in alvos if a.get("type") == "page"), "")
            if not ws_url:
                raise CapturaErro("O Chromium não abriu.")
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
                                raise CapturaErro(f"Chromium: {r['error'].get('message', '')}")
                            return dict(r.get("result", {}))

                async def valor(expressao: str, esperar: bool = False) -> Any:
                    r = await cdp(
                        "Runtime.evaluate",
                        expression=expressao,
                        awaitPromise=esperar,
                        returnByValue=True,
                    )
                    return r.get("result", {}).get("value")

                await cdp("Emulation.setDeviceMetricsOverride", width=largura, height=altura,
                          deviceScaleFactor=1, mobile=False)  # fmt: skip
                await cdp("Page.navigate", url=url)
                for _ in range(150):
                    if await valor("typeof window.pronto") == "object":
                        break
                    await asyncio.sleep(0.1)
                await valor("window.pronto", esperar=True)
                if erros := await valor("(window.Ze && window.Ze.erros) || []"):
                    raise CapturaErro(f"A página do vídeo falhou: {erros[0]}")
                opcoes: dict[str, Any] = {"format": formato}
                if formato == "jpeg":
                    opcoes["quality"] = 92
                for arquivo, t in quadros:
                    await cdp("Runtime.evaluate", expression=f"window.render({t:.4f})")
                    r = await cdp("Page.captureScreenshot", **opcoes)
                    await asyncio.to_thread(arquivo.write_bytes, base64.b64decode(r["data"]))
                    feito()
                if erros := await valor("(window.Ze && window.Ze.erros) || []"):
                    raise CapturaErro(f"A página do vídeo falhou: {erros[0]}")
        finally:
            if proc.returncode is None:
                proc.terminate()
                await proc.wait()


def url_da_pagina(dados: Path, pagina: Path = PAGINA) -> str:
    return (
        f"{pagina.resolve().as_uri()}?dados={urllib.parse.quote(dados.resolve().as_uri(), safe='')}"
    )


def capturar(
    url: str,
    pasta: Path,
    largura: int,
    altura: int,
    duracao: float = 0,
    tempos: list[float] | None = None,
    trabalhadores: int = 0,
    progresso: Callable[[int, int], None] | None = None,
) -> list[Path]:
    """Os quadros (`0000.jpg`...) da página inteira, ou só os `tempos` pedidos (PNG)."""
    binario = navegador()
    if binario is None:
        raise CapturaErro("Chromium não encontrado nesta máquina.")
    pasta.mkdir(parents=True, exist_ok=True)
    if tempos is not None:
        quadros = [(pasta / f"{t:06.2f}.png", t) for t in tempos]
        formato, w = "png", 1
    else:
        quadros = [(pasta / f"{i:04d}.jpg", i / FPS) for i in range(round(duracao * FPS))]
        formato, w = "jpeg", trabalhadores or trabalhadores_padrao()
    contagem = [0]

    def feito() -> None:
        contagem[0] += 1
        if progresso is not None and contagem[0] % 30 == 0:
            progresso(contagem[0], len(quadros))

    async def todos() -> None:
        await asyncio.gather(
            *(
                _trabalhador(binario, url, largura, altura, quadros[k::w], formato, feito)
                for k in range(w)
            )
        )

    inicio = time.monotonic()
    asyncio.run(todos())
    log.info(
        "vídeo: %d quadros em %.0f s (%d em paralelo)", len(quadros), time.monotonic() - inicio, w
    )
    return [q for q, _ in quadros]
