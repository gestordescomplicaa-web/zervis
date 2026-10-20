"""The Teclado: a keyboard icon beside CPU/RAM/GPU/VRAM opens a text bar; what is typed
goes to the Zé (POST /teclado) and its answer shows under the bar.

Run: python tests/test_teclado.py   (or pytest)
Reuses the stage harness of test_brain_navigation.py; the Zé is played by the test.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio
import json
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'jarvis' / 'imersivo' / 'web'  # a página
sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parent)]

import test_brain_navigation as tb  # noqa: E402

CANAL = {'pedidos': [], 'resposta': {}}


class Handler(tb.Handler):
    def do_GET(self):
        if self.path == '/jarvis/teclado-resposta':
            body = json.dumps(CANAL['resposta']).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        out = {}
        if self.path == '/teclado':
            assert self.headers['Content-Type'] == 'application/json'
            out = {'id': f'k{len(CANAL["pedidos"])}'}
            CANAL['pedidos'].append({**d, **out})
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(out).encode())


async def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, passed = [], []
    with tempfile.TemporaryDirectory(prefix='jarvis-teclado-') as profile:
        process = subprocess.Popen([
            '/usr/bin/chromium', '--headless=new', '--remote-debugging-port=0', '--user-data-dir=' + profile,
            '--no-first-run', '--window-size=1440,900', '--disable-background-networking',
            f'http://127.0.0.1:{server.server_port}/stage.html',
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            portfile = Path(profile) / 'DevToolsActivePort'
            for _ in range(100):
                if portfile.exists():
                    break
                await asyncio.sleep(.1)
            port = int(portfile.read_text().splitlines()[0])
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list', timeout=5) as r:
                target = next(p for p in json.load(r) if p['type'] == 'page')
            import websockets
            async with websockets.connect(target['webSocketDebuggerUrl'], max_size=16_000_000) as ws:
                seq = 0

                async def call(method, params=None):
                    nonlocal seq
                    seq += 1
                    await ws.send(json.dumps({'id': seq, 'method': method, 'params': params or {}}))
                    while True:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), 10))
                        if msg.get('method') == 'Runtime.exceptionThrown':
                            errors.append(msg['params'])
                        if msg.get('id') == seq:
                            return msg.get('result', {})

                async def ev(js):
                    r = await call('Runtime.evaluate', {'expression': '{' + js + '\n}', 'returnByValue': True, 'awaitPromise': True})
                    assert 'exceptionDetails' not in r, r
                    return r.get('result', {}).get('value')

                async def check(name, js):
                    assert await ev(js), name
                    passed.append(name)

                async def tecla(key, text=None):
                    base = {'key': key, 'text': text or (key if len(key) == 1 else '')}
                    if key == 'Enter':
                        base.update(code='Enter', windowsVirtualKeyCode=13, text='\r')
                    if key == 'Escape':
                        base.update(code='Escape', windowsVirtualKeyCode=27)
                    await call('Input.dispatchKeyEvent', {'type': 'keyDown', **base})
                    await call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': key})

                await call('Runtime.enable')
                for _ in range(80):
                    if await ev('window.stageReady === true && !!window.jarvisTeclado && !!document.querySelector("#hud-med .m")'):
                        break
                    await asyncio.sleep(.1)
                await check('a keyboard icon sits in the CPU/RAM/GPU/VRAM row', '''(() => { const b = document.querySelector("#hud-m > #jv-teclado-btn");
                    return b && b.querySelector("svg") && document.querySelectorAll("#hud-m .m").length === 4 && document.getElementById("jv-teclado").hidden; })()''')
                await asyncio.sleep(1.7)
                await check('and survives the meters refresh', '!!document.querySelector("#hud-m > #jv-teclado-btn")')

                await ev('document.getElementById("jv-teclado-btn").click()')
                await asyncio.sleep(.1)
                await check('tapping it opens the bar with the cursor in the field', '''!document.getElementById("jv-teclado").hidden
                    && document.activeElement === document.querySelector("#jv-teclado input")''')
                itens = await ev('document.querySelectorAll(".card, .widget, .orb").length')
                for k in 'rdktb':
                    await tecla(k)
                await check('typing letters never fires the shortcuts (R, D, K, T, B)', f'''document.querySelector("#jv-teclado input").value === "rdktb"
                    && document.getElementById("jv-config").hidden && !document.body.classList.contains("tema-ativo")
                    && !jarvisMaos.calibrando && jarvisMaos.brilho === "DESLIGADO"
                    && document.querySelectorAll(".card, .widget, .orb").length === {itens}''')
                await ev('document.querySelector("#jv-teclado input").value = "abra o guia do núcleo"')
                await tecla('Enter')
                for _ in range(30):
                    if CANAL['pedidos']:
                        break
                    await asyncio.sleep(.1)
                assert CANAL['pedidos'] and CANAL['pedidos'][0]['texto'] == 'abra o guia do núcleo', CANAL['pedidos']
                await check('Enter sends the text and clears the field', '''document.querySelector("#jv-teclado input").value === ""
                    && /pensando/.test(document.querySelector("#jv-teclado .resposta").textContent)''')
                CANAL['resposta'] = {'pedido': 'k0', 'texto': 'Guia na tela.', 'fim': False, 'ts': time.time()}
                await asyncio.sleep(.6)
                await check('the answer shows as the Zé speaks it', '''/Guia na tela\\./.test(document.querySelector("#jv-teclado .resposta").textContent)
                    && /pensando/.test(document.querySelector("#jv-teclado .resposta").textContent)''')
                CANAL['resposta'] = {'pedido': 'k0', 'texto': 'Guia na tela.', 'fim': True, 'ts': time.time()}
                await asyncio.sleep(.6)
                await check('and stops waiting when it is done', '!/pensando/.test(document.querySelector("#jv-teclado .resposta").textContent)')
                await tecla('ArrowUp')
                await check('↑ recalls the last request', 'document.querySelector("#jv-teclado input").value === "abra o guia do núcleo"')
                await tecla('Escape')
                await check('Esc closes the bar', 'document.getElementById("jv-teclado").hidden')
                await tecla('/', '/')
                await check('"/" opens it again', '!document.getElementById("jv-teclado").hidden')
                await ev('jarvisControle.executar({id: "t1", acoes: [{acao: "teclado", valor: "fechar"}]})')
                await check('and the Zé can open or close it ("abre o teclado")', 'document.getElementById("jv-teclado").hidden && !jarvisControle.estado().teclado.aberto')
                assert not errors, errors
                print(json.dumps({'passed': len(passed), 'checks': passed}, ensure_ascii=False, indent=2))
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            server.shutdown()
            server.server_close()


def test_teclado():
    asyncio.run(main())


if __name__ == '__main__':
    asyncio.run(main())
