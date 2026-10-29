"""The Foco board (08/10/2026): the Foco view of the Mapa shows the current front big with its
next step and the V to mark it done (pinch or click), the other active fronts smaller and the
rest collapsed; marking posts /foco for the Zé.

Run: python tests/test_avatar.py   (or pytest). WebGL runs on SwiftShader (no GPU needed);
three.js comes from the CDN like the rest of the page.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio
import base64
import json
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'zervis' / 'imersivo' / 'web'  # a página
sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parent)]

import test_brain_navigation as tb  # noqa: E402



async def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), tb.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, passed = [], []
    with tempfile.TemporaryDirectory(prefix='jarvis-foco-', ignore_cleanup_errors=True) as profile:
        process = subprocess.Popen([
            '/usr/bin/chromium', '--headless=new', '--remote-debugging-port=0', '--user-data-dir=' + profile,
            '--no-first-run', '--window-size=1440,900', '--disable-background-networking',
            '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
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
                        msg = json.loads(await asyncio.wait_for(ws.recv(), 20))
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

                await call('Runtime.enable')
                for _ in range(150):
                    if await ev('window.stageReady === true && !!window.jarvisCerebro'):
                        break
                    await asyncio.sleep(.1)
                # Every POST /foco the page makes is recorded (the test server is read-only).
                await ev("""(()=>{window.postsFoco=[];const f=window.fetch;window.fetch=(u,o)=>{
                  if(u==='/foco'){postsFoco.push(JSON.parse(o.body));return Promise.resolve(new Response('{"ok":true}'));}
                  return f(u,o);};})()""")
                await ev('jarvisControle.executar({id: "f1", acoes: [{acao: "foco"}]})')
                await asyncio.sleep(1.2)
                await check('"mostra o meu foco" opens the Foco view on the board, not an item', """(() => {
                    const q = document.querySelector('#jv-mapa .vista.focus:not([hidden]) .foco-quadro');
                    return q && q.querySelector('.foco-cartao.atual h2').textContent === 'Lançar o Ligatia'
                      && jarvisCerebro.estado().modo === 'foco'; })()""")
                shot = await call('Page.captureScreenshot', {'format': 'png'})
                Path('/tmp/jarvis-foco.png').write_bytes(base64.b64decode(shot['data']))
                await check('the current front is big, with its next step behind a V', """(() => {
                    const v = document.querySelector('.foco-cartao.atual .foco-v');
                    return v && v.textContent.includes('comparar provedores SIP')
                      && v.querySelector('.caixa').getBoundingClientRect().width >= 50; })()""")
                await check('the other active front is a smaller card; the rest is counted and collapsed', """(() => {
                    const outras = [...document.querySelectorAll('.foco-outras .foco-cartao h2')].map(x => x.textContent);
                    const grupos = [...document.querySelectorAll('.foco-grupos button')].map(x => x.textContent);
                    return outras.join() === 'Site novo' && grupos.join() === 'Travadas (1),Ideias (1)'
                      && !document.querySelector('.foco-lista')
                      && document.querySelector('.foco-topo').textContent.includes('2 concluídas hoje'); })()""")
                # The V by pinch, through the same hand path the tracker feeds.
                await ev("""(()=>{const r=document.querySelector('.foco-cartao.atual .foco-v').getBoundingClientRect();
                  const x=r.left+30,y=r.top+r.height/2;
                  jarvisBrainGestures.hand({id:1,x,y,pinched:true});jarvisBrainGestures.hand({id:1,x,y,pinched:false});})()""")
                await asyncio.sleep(.3)
                await check('pinching the V marks the step done at once and tells the Zé', """(() =>
                    JSON.stringify(postsFoco) === JSON.stringify([{acao:'passo',id:'ligatia'}])
                    && document.querySelector('.foco-cartao.atual .foco-v').classList.contains('marcado'))()""")
                await ev("document.querySelector('[data-action=\"foco-grupo:travadas\"]').click()")
                await asyncio.sleep(.2)
                await check('opening Travadas shows why it is stuck, with Retomar', """(() => {
                    const i = document.querySelector('.foco-lista .foco-item');
                    return i && i.textContent.includes('Vídeo do Zé — microfone novo') && i.textContent.includes('Retomar'); })()""")
                await ev("document.querySelector('.foco-outras [data-action=\"foco:focar:site-novo\"]').click()")
                await ev("document.querySelector('.foco-cartao.atual [data-action=\"foco:concluir:ligatia\"]').click()")
                await asyncio.sleep(.2)
                await check('focus on another front and mark a front finished, by click too', """(() =>
                    postsFoco.slice(1).map(p=>p.acao+':'+p.id).join() === 'focar:site-novo,concluir:ligatia')()""")
                # Nothing in progress, only ideas (08/10/2026: the user saw an empty board and got lost).
                await ev("""(()=>{const f=window.fetch;window.fetch=(u,o)=>u==='/jarvis/foco'
                  ?Promise.resolve(new Response(JSON.stringify({atual:null,ativas:[],travadas:[],pausadas:[],
                    ideias:[{id:'academia',titulo:'Começar a academia em novembro'}],concluidas_hoje:0,limite:3})))
                  :f(u,o);})()""")
                await ev('jarvisCerebro.mostrarFoco()')
                await asyncio.sleep(.3)
                await check('with nothing in progress the ideas show by themselves, each with Virar frente', """(() => {
                    const vazio = document.querySelector('.foco-vazio'), i = document.querySelector('.foco-lista .foco-item');
                    return vazio && vazio.textContent.includes('Virar frente') && i
                      && i.textContent.includes('Começar a academia') && i.querySelector('button').textContent === 'Virar frente'; })()""")
                await ev("document.querySelector('.foco-lista [data-action=\"foco:focar:academia\"]').click()")
                await ev("document.querySelector('[data-action=\"foco-grupo:ideias\"]').click()")
                await asyncio.sleep(.2)
                await check('Virar frente starts the idea; the ideas still collapse on demand', """(() =>
                    postsFoco.at(-1).acao + ':' + postsFoco.at(-1).id === 'focar:academia'
                    && !document.querySelector('.foco-lista'))()""")
                await ev("document.querySelector('[data-action=\"mode:brain\"]').click()")
                await asyncio.sleep(.3)
                await check('the other Mapa views still work', "jarvisCerebro.estado().modo === 'cerebro'")
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


def test_foco_na_tela():
    asyncio.run(main())


if __name__ == '__main__':
    asyncio.run(main())
