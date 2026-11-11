"""The opening (ADR 0078): opening the program lands on the stage with ?abertura=1; the music
plays, the name lights up and the Zé presents the day, one panel per block, each spoken in his
voice (POST /abertura/falar with the step; GET /orb tells when he stops speaking). The address
forgets the request, Esc skips it, and the "apresentar dia" action replays it.

Run: python tests/imersivo/test_abertura.py   (or pytest with ZE_TESTES_IMERSIVO=1)
Reuses the stage harness of test_brain_navigation.py; the Zé is played by the test.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio
import io
import json
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import wave
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parent)]

import test_brain_navigation as tb  # noqa: E402

MONTADO = '2026-11-11T09:00:00-03:00'
DIA = {'montado': MONTADO, 'ligada': True, 'blocos': [
    {'tipo': 'relogio', 'saudacao': 'Bom dia, Ana', 'data': 'quarta-feira, 11 de novembro', 'fala': 'Bom dia, Ana.'},
    {'tipo': 'clima', 'cidade': 'Fortaleza', 'temperatura': 30, 'ceu': 'garoa fraca', 'maxima': 31, 'minima': 24, 'chuva': 40, 'fala': 'Faz 30 graus.'},
    {'tipo': 'hoje', 'itens': [{'hora': '14:00', 'titulo': 'Reunião', 'tipo': 'compromisso'}, {'hora': '18:00', 'titulo': 'Relatório', 'tipo': 'automacao'}], 'total': 2, 'fala': 'Dois itens.'},
    {'tipo': 'sessoes', 'itens': [{'nome': 'Loja', 'situacao': 'Interrompida', 'chave': 'interrompida'}], 'total': 1, 'fala': 'A Loja parou.'},
    {'tipo': 'whatsapp', 'itens': [{'nome': '<b>Ana</b>', 'ha': 'há 1 h'}], 'total': 1, 'fala': 'Uma conversa.'},
    {'tipo': 'noticias', 'itens': [{'titulo': 'Manchete', 'fonte': 'G1'}], 'fala': 'Manchete.'},
    {'tipo': 'fim', 'fala': 'Esse é o seu dia.'},
]}
CANAL: dict = {'falas': [], 'fala_ate': 0.0, 'musica': 0}
SAIDA = Path(tempfile.gettempdir()) / 'jarvis-abertura.png'


def _wav() -> bytes:
    saida = io.BytesIO()
    with wave.open(saida, 'wb') as w:
        w.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
        w.writeframes(b'\0\0' * 8000 * 3)
    return saida.getvalue()


class Handler(tb.Handler):
    def _enviar(self, body, kind='application/json', code=200):
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/abertura':
            self._enviar(json.dumps(DIA).encode())
        elif self.path == '/abertura/musica':
            CANAL['musica'] += 1
            self._enviar(_wav(), 'audio/wav')
        elif self.path == '/orb':  # speaking while the line plays
            falando = time.time() < CANAL['fala_ate']
            self._enviar(json.dumps({'state': 'speaking' if falando else 'idle', 'mood': 'green', 'wave': None}).encode())
        else:
            super().do_GET()

    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path == '/abertura/falar':
            assert self.headers['Content-Type'] == 'application/json'
            CANAL['falas'].append(d)
            CANAL['fala_ate'] = time.time() + .5
        self._enviar(b'{}')


async def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, passed = [], []
    with tempfile.TemporaryDirectory(prefix='jarvis-abertura-') as profile:
        process = subprocess.Popen([
            '/usr/bin/chromium', '--headless=new', '--remote-debugging-port=0', '--user-data-dir=' + profile,
            '--no-first-run', '--window-size=1280,720', '--disable-background-networking',
            '--autoplay-policy=no-user-gesture-required',  # the launcher's flag (deploy/abrir-painel.sh)
            f'http://127.0.0.1:{server.server_port}/stage.html?res=1280x720&abertura=1',
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
                assert await esperar('!!window.jarvisAbertura && !!document.getElementById("jv-abertura-vinheta")'), 'no opening title'
                passed.append('opening the program shows the name over the music')
                assert await ev('!location.search.includes("abertura") && location.search.includes("res=1280x720")')
                passed.append('the address forgets the request (a reload does not repeat it)')
                assert CANAL['musica'] == 1
                passed.append('the music of whoever uses the Zé is fetched')
                # One subject at a time: a panel only comes with its own line, never ahead of it.
                adiantados = []
                fim = time.monotonic() + 40
                while time.monotonic() < fim:
                    paineis = await ev('document.querySelectorAll(".card.jv-holo.jv-ab").length')
                    if paineis > len(CANAL['falas']):
                        adiantados.append((paineis, len(CANAL['falas'])))
                    if paineis == 6:
                        break
                    await asyncio.sleep(.05)
                assert paineis == 6, paineis
                assert await ev('!document.getElementById("jv-legenda-ze").textContent')
                assert not adiantados, adiantados
                passed.append('one panel per block, each one only with its own line, in order, no caption')
                assert await esperar('!jarvisAbertura.rodando', 30), CANAL['falas']
                assert [f['passo'] for f in CANAL['falas']] == list(range(7)), CANAL['falas']
                assert all(f['montado'] == MONTADO and set(f) == {'montado', 'passo'} for f in CANAL['falas'])
                passed.append('each step asks the Zé for its own line, only by number, then the closing one')
                assert await ev('''(() => { const t = [...document.querySelectorAll(".jv-ab h2")].map(h => h.textContent);
                    return t.join("|") === "Hoje|Fortaleza|Hoje|Sessões de código|Sem resposta|Manchetes"
                      && /^\\d\\d:\\d\\d$/.test(document.querySelector("[data-relogio]").textContent)
                      && document.querySelector(".jv-ab-clima b").textContent === "30°"
                      && !document.querySelector(".jv-ab b b")
                      && !document.querySelector("#jv-feixes"); })()''')
                passed.append('the panels show the Zé\'s data, escaped, with a live clock, and no beams across them')
                assert await ev('!document.getElementById("jv-abertura-vinheta")')
                passed.append('the panels stay on the board when it is over; the title is gone')
                import base64
                SAIDA.write_bytes(base64.b64decode((await call('Page.captureScreenshot', {'format': 'png'}))['data']))

                # The music is not a media player (MPRIS): the Zé pauses those while he speaks.
                await ev('window.__tocou = 0; const tocar = HTMLMediaElement.prototype.play;'
                         'HTMLMediaElement.prototype.play = function () { window.__tocou++; return tocar.call(this); };')
                r = await ev('jarvisAbertura.iniciar().then(r => r.musica)')
                assert r == 'arquivo' and CANAL['musica'] == 2, r
                assert await ev('window.__tocou === 0')
                await ev('jarvisAbertura.encerrar()')
                passed.append('the music plays by Web Audio, not as a media player the Zé would pause')

                CANAL['falas'].clear()
                r = await ev('jarvisControle.executar({id:"d1",acoes:[{acao:"apresentar",valor:"dia"}]})')
                assert await esperar('jarvisAbertura.rodando', 5), r
                assert CANAL['musica'] == 2
                passed.append('"apresentar dia" replays the day, without the music')
                assert await esperar('jarvisAbertura.falados.length >= 2', 15)
                await call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27})
                await call('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': 'Escape'})
                assert await esperar('!jarvisAbertura.rodando && !document.querySelector(".card.jv-holo")', 8)
                falas = len(CANAL['falas'])
                await asyncio.sleep(2.5)
                assert len(CANAL['falas']) == falas, CANAL['falas']
                passed.append('Esc skips it: the panels go and no more lines are asked for')
                assert not errors, errors
                print('\n'.join('PASS ' + p for p in passed))
        finally:
            process.kill()
            server.shutdown()
            server.server_close()


def test_a_abertura():
    asyncio.run(main())


if __name__ == '__main__':
    asyncio.run(main())
