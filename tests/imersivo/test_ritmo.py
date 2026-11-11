"""A scene in the rhythm of the Zé's voice (jarvis-ritmo.js): each step of an "explicar" scene
waits for his voice to reach its line. GET /orb is played by the test: thinking first, then the
chunks the voice says (state/fala.json) and how far into each one it is.

Run: python tests/imersivo/test_ritmo.py   (or pytest with ZE_TESTES_IMERSIVO=1)
Reuses the stage harness of test_brain_navigation.py.
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

FALAS = ['Hoje vou explicar o ciclo da água.',
         'Primeiro o sol aquece os oceanos e a água evapora.',
         'Depois o vapor esfria nas nuvens e volta como chuva.']
CENA = {'titulo': 'Ciclo da água', 'passos': [
    {'fala': FALAS[0], 'blocos': [{'tipo': 'titulo', 'texto': 'Ciclo da água'}]},
    {'fala': FALAS[1], 'blocos': [{'tipo': 'lista', 'titulo': 'Evaporação', 'itens': ['sol', 'oceano']}]},
    {'fala': FALAS[2], 'blocos': [{'tipo': 'lista', 'titulo': 'Chuva', 'itens': ['nuvem', 'chuva']}]},
]}
# What the voice says: the first sentence alone, then the rest in one chunk (zervis/voz/saida.py),
# as the voice text (numbers in words; here there are none).
RESTO = f'{FALAS[1]} {FALAS[2]}'
ORB: dict = {'state': 'thinking'}


class Handler(tb.Handler):
    def do_GET(self):
        if self.path == '/orb':
            body = json.dumps({'mood': 'green', **ORB}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()


def falando(texto, ate, inicio):
    ORB.clear()
    ORB.update({'state': 'speaking', 'fala': {'texto': texto, 'ate': ate, 'inicio': inicio}})


async def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, passed = [], []
    with tempfile.TemporaryDirectory(prefix='jarvis-ritmo-') as profile:
        process = subprocess.Popen([
            '/usr/bin/chromium', '--headless=new', '--remote-debugging-port=0', '--user-data-dir=' + profile,
            '--no-first-run', '--window-size=1280,720', '--disable-background-networking',
            f'http://127.0.0.1:{server.server_port}/stage.html?res=1280x720',
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

                async def esperar(js, limite=10.0):
                    fim = time.monotonic() + limite
                    while time.monotonic() < fim:
                        if await ev(js):
                            return True
                        await asyncio.sleep(.1)
                    return False

                await call('Runtime.enable')
                assert await esperar('window.stageReady === true && !!window.jarvisRitmo && !!window.jarvisCenas', 15)
                blocos = 'document.querySelectorAll(".card.jv-holo.jv-cena").length'

                # The line of each step is found in what the voice says, numbers and accents aside.
                assert await ev(f'''const r = jarvisRitmo, ws = r.palavras({json.dumps(RESTO)});
                    const j = r.achar(ws, r.chave({json.dumps(FALAS[2])}));
                    j > 0 && {json.dumps(RESTO)}.slice(ws[j].i).startsWith("Depois")
                      && r.achar(r.palavras("o voo tem trezentos e quarenta km"), r.chave("O voo tem 340 km")) === 1
                      && r.achar(ws, r.chave("Nada a ver com isto aqui.")) === -1''')
                passed.append("a step's line is found in the voice's text (numbers said in words, accents aside)")

                # 1. While he thinks, only the first step: the scene no longer runs ahead of him.
                await ev(f'jarvisApresentacao.ritmo = .3; jarvisCenas.explicar({json.dumps(CENA)}); 1')
                assert await esperar(f'{blocos} === 1', 5)
                await asyncio.sleep(3)
                assert await ev(f'{blocos} === 1'), 'the scene ran ahead while the Zé was thinking'
                passed.append('while the Zé thinks, the scene holds on its first step')

                # 2. He says the first sentence: still the first step.
                agora = time.time()
                falando(FALAS[0], len(FALAS[0]), agora)
                await asyncio.sleep(1.5)
                assert await ev(f'{blocos} === 1')
                # 3. The next chunk starts with the second step's line: it comes.
                falando(RESTO, 4, agora + 3)
                assert await esperar(f'{blocos} === 2', 4), 'the second step did not come with its line'
                passed.append('a step comes when the voice reaches its line')
                # 4. Halfway through the second sentence, the third step waits.
                depois = RESTO.index('Depois')
                falando(RESTO, depois - 12, agora + 3)
                await asyncio.sleep(2)
                assert await ev(f'{blocos} === 2'), 'the third step came before its line'
                falando(RESTO, depois + 3, agora + 3)
                assert await esperar(f'{blocos} === 3', 4)
                passed.append('and not before: the board waits while he still talks about the last blocks')
                ORB.clear()
                ORB.update({'state': 'idle'})

                # 5. No voice at all (silent mode, an answer that never comes): the reading time.
                await ev('jarvisApresentacao.encerrar(); 1')
                await asyncio.sleep(.5)
                await ev(f'jarvisApresentacao.ritmo = .05; jarvisCenas.explicar({json.dumps(CENA)}); 1')
                assert await esperar(f'{blocos} === 3', 10), 'without a voice the scene got stuck'
                passed.append('without a voice to follow, the scene still plays at reading pace')
                await ev('jarvisApresentacao.encerrar(); 1')
                assert not errors, errors
                print('\n'.join('PASS ' + p for p in passed))
        finally:
            process.kill()
            server.shutdown()
            server.server_close()


def test_a_cena_no_ritmo_da_voz():
    asyncio.run(main())


if __name__ == '__main__':
    asyncio.run(main())
