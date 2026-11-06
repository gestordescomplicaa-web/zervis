"""The loading bar (ADR 0064): while the Zé thinks, what he is doing and a bar that moves like a
game's; full and gone once the answer starts.

Run: python tests/imersivo/test_andamento.py   (or pytest with ZE_TESTES_IMERSIVO=1)
Reuses the stage harness of test_brain_navigation.py; GET /orb is played by the test.
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

sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parent)]

import test_brain_navigation as tb  # noqa: E402

ORB: dict = {'state': 'idle', 'mood': 'green', 'wave': None}
SAIDA = Path(tempfile.gettempdir()) / 'jarvis-andamento.png'


class Handler(tb.Handler):
    def do_GET(self):
        if self.path == '/orb':
            body = json.dumps(ORB).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()


async def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, passed = [], []
    with tempfile.TemporaryDirectory(prefix='jarvis-andamento-') as profile:
        process = subprocess.Popen([
            '/usr/bin/chromium', '--headless=new', '--remote-debugging-port=0', '--user-data-dir=' + profile,
            '--no-first-run', '--window-size=1280,720', '--disable-background-networking',
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

                async def esperar(js, limite=8.0):
                    fim = time.monotonic() + limite
                    while time.monotonic() < fim:
                        if await ev(js):
                            return True
                        await asyncio.sleep(.1)
                    return False

                await call('Runtime.enable')
                assert await esperar('window.stageReady === true && !!window.jarvisAndamento', 15)
                assert await ev('!document.getElementById("jv-andamento").classList.contains("ativo")')
                passed.append('idle: no bar')

                ORB.update(state='thinking')
                assert await esperar('document.getElementById("jv-andamento").classList.contains("ativo")')
                ORB['andamento'] = {'rotulo': 'Pesquisando a fundo na internet', 'esperado_s': 12, 'ts': time.time()}
                assert await esperar('document.querySelector("#jv-andamento .rotulo").textContent.startsWith("Pesquisando a fundo na internet…")')
                await asyncio.sleep(1.5)
                largura = await ev('parseFloat(document.querySelector("#jv-andamento .cheio").style.width)')
                assert 3 < largura < 95, largura  # moving, never full before the answer
                passed.append('thinking: the step label and a moving bar below 95%')
                shot = await call('Page.captureScreenshot', {'format': 'png'})
                import base64
                SAIDA.write_bytes(base64.b64decode(shot['data']))

                ORB.update(state='speaking')
                ORB.pop('andamento')
                assert await esperar('document.querySelector("#jv-andamento .cheio").style.width === "100%"', 5)
                assert await esperar('!document.getElementById("jv-andamento").classList.contains("ativo")', 5)
                passed.append('speaking: the bar fills and goes away')
                assert not errors, errors
                print('\n'.join('PASS ' + p for p in passed))
        finally:
            process.kill()
            server.shutdown()
            server.server_close()


def test_a_barra_de_carregamento():
    asyncio.run(main())


if __name__ == '__main__':
    asyncio.run(main())
