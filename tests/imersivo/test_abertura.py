"""The opening (ADR 0078): opening the program lands on the stage with ?abertura=1; the music
plays, the name lights up and the Zé presents the day, one scene per block, each spoken in his
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
HORAS = [24, 24, 23, 23, 24, 25, 26, 27, 28, 29, 30, 31, 31, 31, 30, 29, 28, 27, 26, 26, 25, 25, 24, 24]
CHUVA = [0, 0, 0, 0, 0, 0, 10, 10, 20, 20, 30, 40, 60, 70, 80, 70, 50, 40, 30, 20, 10, 0, 0, 0]
# The day by the Zé's menu: now, today, social networks, activity, what is pending, headlines.
DIA = {'montado': MONTADO, 'ligada': True, 'blocos': [
    {'tipo': 'agora', 'saudacao': 'Bom dia, Ana', 'data': 'quarta-feira, 11 de novembro', 'fala': 'Bom dia, Ana.',
     'clima': {'cidade': 'Fortaleza', 'temperatura': 30, 'ceu': 'garoa fraca', 'maxima': 31, 'minima': 24, 'chuva': 40,
               'horas': HORAS, 'chuva_horas': CHUVA, 'icone': 'chuva'}},
    {'tipo': 'hoje', 'total': 2, 'fala': 'Dois itens.',
     'itens': [{'hora': '14:00', 'titulo': 'Reunião', 'tipo': 'compromisso', 'chuva': True},
               {'hora': '18:00', 'titulo': 'Relatório', 'tipo': 'automacao', 'chuva': False}],
     'foco': {'atual': 'Lançar a loja', 'proximo_passo': 'subir as fotos', 'ativas': 2, 'travadas': 1, 'pausadas': 0, 'feitas_semana': 3}},
    {'tipo': 'redes', 'fala': 'Uma conversa.',
     'whatsapp': {'itens': [{'nome': '<b>Ana</b>', 'ha': 'há 1 h', 'min': 60}], 'total': 1},
     'instagram': {'usuario': 'ana.loja', 'seguidores': 15300, 'semana': 2, 'destaque': {'legenda': 'Promoção', 'valor': '12 mil'},
                   'grafico': [{'rotulo': '01/11', 'valor': 30000}, {'rotulo': '08/11', 'valor': 4000}, {'rotulo': '10/11', 'valor': 12000}]}},
    {'tipo': 'atividade', 'dias': 7, 'pedidos': 120, 'acoes': 340, 'falhas': 12, 'automacoes': 2, 'sessoes': ['Site'], 'fala': 'Atendi 120 pedidos.',
     'por_dia': [{'dia': '2026-11-09', 'registros': 50, 'falhas': 2}, {'dia': '2026-11-10', 'registros': 80, 'falhas': 4},
                 {'dia': '2026-11-11', 'registros': 30, 'falhas': 1}]},
    {'tipo': 'pendencias', 'total': 2, 'fala': 'Dois itens pedem você.',
     'itens': [{'area': 'Sessões', 'titulo': 'Loja', 'detalhe': 'Interrompida', 'nivel': 'alerta'},
               {'area': 'Atualizações', 'titulo': 'Nova versão', 'detalhe': 'Disponível', 'nivel': 'info'}],
     'areas': [{'area': 'Sessões', 'n': 1}, {'area': 'Atualizações', 'n': 1}]},
    {'tipo': 'noticias', 'itens': [{'titulo': 'Manchete', 'fonte': 'G1'}], 'fala': 'Manchete.'},
    {'tipo': 'fim', 'fala': 'Esse é o seu dia.'},
]}
# The Zé has just started (opening the program starts him): his first panoramas come before the
# weather, the Instagram and the headlines. The page waits for the complete one.
INCOMPLETO = {'montado': '2026-11-11T08:59:58-03:00', 'ligada': True, 'completo': False,
              'blocos': [{**DIA['blocos'][0], 'clima': None}, DIA['blocos'][1], DIA['blocos'][-1]]}
DIA['completo'] = True
CANAL: dict = {'falas': [], 'sinais': [], 'fala_ate': 0.0, 'musica': 0, 'panoramas': 0}
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
            CANAL['panoramas'] += 1
            self._enviar(json.dumps(INCOMPLETO if CANAL['panoramas'] <= 12 else DIA).encode())
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
        if self.path == '/abertura/falar' and d['passo'] < 0:  # began (-1) or skipped (-2): no line
            CANAL['sinais'].append(d['passo'])
        elif self.path == '/abertura/falar':
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
                        # a headless Chromium only draws (and runs the board's animations) on demand
                        await call('Page.captureScreenshot', {'format': 'jpeg', 'quality': 20})
                        await asyncio.sleep(.05)
                    return False

                await call('Runtime.enable')
                assert await esperar('!!window.jarvisAbertura && !!document.getElementById("jv-abertura-vinheta")'), 'no opening title'
                passed.append('opening the program shows the name over the music')
                assert await ev('!location.search.includes("abertura") && location.search.includes("res=1280x720")')
                passed.append('the address forgets the request (a reload does not repeat it)')
                assert CANAL['musica'] == 1
                passed.append('the music of whoever uses the Zé is fetched')
                assert await esperar('document.querySelectorAll("#jv-abertura-vinheta .cenas span").length === 6')
                passed.append('under the name, the scenes of the day light up once the Zé has the full day')
                # One subject at a time: a scene only comes with its own line, never ahead of it,
                # and it is the only one large at the centre.
                adiantados, herois = [], []
                fim = time.monotonic() + 40
                while time.monotonic() < fim:
                    paineis, grandes = await ev('[document.querySelectorAll(".card.jv-holo.jv-ab").length,'
                                                ' document.querySelectorAll(".card.jv-holo.jv-ab.heroi").length]')
                    herois.append(grandes)
                    if paineis > len(CANAL['falas']):
                        adiantados.append((paineis, len(CANAL['falas'])))
                    if paineis == 6:
                        break
                    await asyncio.sleep(.05)
                assert paineis == 6, paineis
                assert await ev('!document.getElementById("jv-legenda-ze").textContent')
                assert not adiantados, adiantados
                assert max(herois) == 1, herois
                passed.append('one scene per block, each one only with its own line, large at the centre, no caption')
                assert await esperar('!jarvisAbertura.rodando', 30), CANAL['falas']
                assert [f['passo'] for f in CANAL['falas']] == list(range(7)), CANAL['falas']
                assert CANAL['sinais'] == [-1], CANAL['sinais']
                passed.append('the opening tells the Zé it began, so his notices wait until it is over')
                assert all(f['montado'] == MONTADO and set(f) == {'montado', 'passo'} for f in CANAL['falas'])
                passed.append('each step asks the Zé for its own line, only by number, then the closing one')
                passed.append('the page waits for the complete panorama, not the one from before the first fetch')
                assert await ev('''(() => { const t = [...document.querySelectorAll(".jv-ab h2")].map(h => h.textContent);
                    return t.join("|") === "Agora|Hoje|Redes sociais|Atividade|Pendências|Manchetes"
                      && /^\\d\\d:\\d\\d$/.test(document.querySelector("[data-relogio]").textContent)
                      && /^\\d\\d$/.test(document.querySelector("[data-segundo]").textContent)
                      && document.querySelector(".jv-ab-clima > b").textContent === "30°"
                      && document.querySelector(".jv-ab-whats .txt").textContent === "<b>Ana</b>"
                      && !document.querySelector("#jv-feixes"); })()''')
                passed.append('the scenes follow the menu and show the Zé\'s data, escaped, with a live clock')
                assert await esperar('''document.querySelector(".jv-ab-tempo path.linha")?.getAttribute("d").split("C").length === 24
                    && document.querySelectorAll(".jv-ab-tempo .chuva rect").length === 15
                    && !!document.querySelector(".jv-ab-ceu .gotas")
                    && document.querySelectorAll(".jv-ab-mostrador .marca").length === 2
                    && document.querySelectorAll(".jv-ab-frentes i").length === 3
                    && document.querySelectorAll(".jv-ab-chuva").length === 1
                    && document.querySelectorAll(".jv-ab-insta .jv-grafico svg .jv-coluna").length === 3
                    && document.querySelectorAll(".jv-ab-atividade .jv-grafico svg .jv-coluna").length === 3
                    && document.querySelectorAll(".jv-ab-anel .arco").length === 2
                    && document.querySelector(".jv-ab-insta .jv-heroi b").textContent.replace(/\\s/g, " ") === "15,3 mil"
                    && document.querySelector(".jv-ab-anel b").textContent === "2"
                    && document.querySelector(".jv-ab-atividade [data-n]").textContent === "120"
                    && document.querySelectorAll(".jv-ab-fita span").length === 2''', 8)
                passed.append('charts: the day\'s temperature and rain, the day\'s dial, the fronts, the views, the activity, the pending ring')
                assert await esperar('''(() => { const r = [...document.querySelectorAll(".card.jv-holo.jv-ab")].map(e => e.getBoundingClientRect());
                    return !document.querySelector(".jv-ab.heroi")
                      && r.every((a, i) => r.every((b, j) => i === j || a.right <= b.left + 1 || b.right <= a.left + 1
                      || a.bottom <= b.top + 1 || b.bottom <= a.top + 1))
                      && r.every(a => a.left >= innerWidth * .2 && a.right <= innerWidth + 1 && a.top >= 0 && a.bottom <= innerHeight); })()''', 8)
                passed.append('the scenes dock into a mosaic with the headlines under it: none over another, all on the screen')
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
                assert CANAL['sinais'][-1] == -2, CANAL['sinais']
                passed.append('Esc skips it: the panels go, no more lines are asked for, and the Zé is told')
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
