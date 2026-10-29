"""Browser regressions for the local Zé map patch (no webcam or live writes).

Run with Python + websockets: python tests/test_brain_navigation.py
Uses installed Chromium and an isolated HTTP server/browser profile.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio
import base64
import json
import subprocess
import tempfile
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[2] / 'zervis' / 'imersivo' / 'web'  # a página
EVENTS = [
    {'em': 1791330000 - i * 3600, 'evento': 'aprovada', 'rotulo': 'Sugestão aprovada',
     'resumo': f'guardar a lição {i}', 'origem': f'correção {i}', 'item': None} for i in range(1, 25)]
MAP = {
    'centro': {'rotulo': 'Zé', 'sub': 'Claude, com o Sonnet 5.5'},
    'grupos': [
        {'id': 'usuario', 'rotulo': 'Sobre você', 'itens': [
            {'id': 'usuario:a', 'rotulo': 'Prefere escolher…', 'texto': 'Prefere escolher na tela',
             'origem': 'Mostre as opções', 'em': 1791330000, 'novo': True},
            {'id': 'usuario:b', 'rotulo': 'Texto <seguro>',
             'texto': '<img src=x onerror="window.injected=true">', 'novo': False},
        ]},
        {'id': 'jarvis', 'rotulo': 'Ambiente', 'itens': []},
        {'id': 'skills', 'rotulo': 'Skills', 'itens': []},
        {'id': 'automacoes', 'rotulo': 'Automações', 'itens': []},
    ],
    'linha_do_tempo': [{'em': 1791330000, 'evento': 'aprovada', 'rotulo': 'Sugestão aprovada',
                        'resumo': 'guardar na memória sobre você: Prefere escolher na tela',
                        'origem': 'Mostre as opções', 'item': 'usuario:a'}] + EVENTS,
    'por_dia': [{'dia': f'{d:02d}/10', 'n': d % 3} for d in range(1, 15)],
    'aprendizado': {'aprovadas': 25, 'recentes': 1},
}
SUGGESTIONS = [{'resumo': 'criar a skill <b>x</b>', 'origem': 'faça assim'}]

# Run the exact stage routing block, with detected hand samples in place of
# MediaPipe. This catches wiring regressions as well as controller behaviour.
stage = (ROOT / 'stage.html').read_text()
bridge = stage.split('        // barehands-jarvis: the brain map owns', 1)[1].split('        // ---- THE PALM ENGINE', 1)[0]
bridge = '// barehands-jarvis: the brain map owns' + bridge
# Use the original stage itself. Only the external hand tracker and camera boot
# are replaced; ring, bloom, physics, tap discrimination and routing stay real.
HARNESS = stage.replace(
    'import { HandLandmarker, FilesetResolver } from\n  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs";',
    'const HandLandmarker = null, FilesetResolver = null;')
a = HARNESS.index('  boot().catch(e => {')
b = HARNESS.index('  });', a) + len('  });')
test_boot = '''
  document.getElementById('boot').remove();
  window.stageHitTest = hitTest;
  window.boardCalls = 0;
  window.stagePinch = selector => {
    const c = items.find(i => i.el.matches(selector) && i.anim?.k !== 'out');
    const cur = {x:c.x,y:c.y,history:[{x:c.x,y:c.y,t:10},{x:c.x,y:c.y,t:30}]};
    beginGrab(c,99,cur); endGrab(c,99,cur);
  };
  window.feedTrackedHand = function(cur,i,wasPinched,now,hspd=0) {
    const handGarbage=false,tip={x:cur.x,y:cur.y};let brainGestureCaptured=false;
    cur.el ||= document.createElement('div');
    BRIDGE
    window.boardCalls++;
  };
  loadTree().then(()=>{
    spawnStage();
    window.stageReady=true;
    const animate=()=>{physics(1/60);drawStageConnections();renderRings();requestAnimationFrame(animate);};
    requestAnimationFrame(animate);
  });
'''.replace('BRIDGE', bridge)
HARNESS = HARNESS[:a] + test_boot + HARNESS[b:]
CONFIG = {'name': 'ZÉ', 'orbs': [
    {'id': 'mapa', 'title': 'Mapa', 'kind': 'brain', 'apelidos': ['cérebro', 'seu cérebro']},
    {'id': 'guia', 'title': 'Guia', 'kind': 'notes', 'apelidos': ['manual']},
    {'id': 'hoje', 'title': 'Hoje', 'kind': 'hoje', 'apelidos': ['meu dia']},
    {'id': 'trabalho', 'title': 'Trabalho', 'kind': 'trabalho', 'apelidos': ['sessões']},
    {'id': 'acervo', 'title': 'Acervo', 'kind': 'media', 'apelidos': ['arquivos']}]}
# The coding sessions of the Zé (state/trabalho.json).
TRABALHO = {'disponivel': True, 'sessoes': [
    {'id': 'a', 'rotulo': 'Loja', 'estado': 'trabalhando', 'pasta': 'loja', 'texto': 'Testes passando.'},
    {'id': 'b', 'rotulo': 'Site', 'estado': 'parada', 'pasta': 'site', 'texto': ''}]}



# The Foco board (written by the Zé into state/foco.json).
FOCO = {
    'atual': {'id': 'ligatia', 'titulo': 'Lançar o Ligatia', 'proximo_passo': 'comparar provedores SIP',
              'bloqueio': '', 'projeto': 'Ligatia', 'mexida': '08/10 16:00'},
    'ativas': [{'id': 'site-novo', 'titulo': 'Site novo', 'proximo_passo': 'escolher o tema',
                'bloqueio': '', 'projeto': '', 'mexida': '08/10 15:00'}],
    'travadas': [{'id': 'video', 'titulo': 'Vídeo do Zé', 'proximo_passo': '', 'bloqueio': 'microfone novo',
                  'projeto': '', 'mexida': '08/10 14:00'}],
    'pausadas': [], 'ideias': [{'id': 'app', 'titulo': 'App de receitas', 'proximo_passo': '', 'bloqueio': '',
                                'projeto': '', 'mexida': '08/10 13:00'}],
    'concluidas_hoje': 2, 'limite': 3, 'ts': 9_999_999_999,
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/stage.html'):
            body, kind = HARNESS.encode(), 'text/html'
        elif self.path in ['/jarvis-paineis.js', '/jarvis-cerebro.js', '/jarvis-grafo.js', '/jarvis-workspace.css', '/jarvis-maos.js', '/jarvis-tema.js', '/jarvis-fundo.js', '/jarvis-tema.css', '/jarvis-config.js', '/jarvis-controle.js', '/jarvis-teclado.js', '/jarvis-avatar.js', '/jarvis-apresentacao.js', '/jarvis-apresentacao.css', '/avatar/jarvis-chimpanze.js', '/avatar/jarvis-constelacao.js', '/avatar/jarvis-chimpanze.glb', '/avatar/jarvis-chimpanze-frente.png', '/avatar/jarvis-chimpanze-perfil.png', '/avatar/jarvis-chimpanze-costas.png']:
            body, kind = (ROOT / self.path.removeprefix('/')).read_bytes(), 'text/css' if self.path.endswith('.css') else 'model/gltf-binary' if self.path.endswith('.glb') else 'image/png' if self.path.endswith('.png') else 'text/javascript'
        elif self.path == '/autoconhecimento':  # the sample the panel test also uses, no one's data
            body = json.dumps(json.loads((Path(__file__).parents[1] / 'painel_respostas.json').read_text())['leituras']['autoconhecimento']).encode()
            kind = 'application/json'
        elif self.path.startswith('/jarvis/'):
            name = self.path.removeprefix('/jarvis/')
            data = {'mapa': MAP, 'decisao': {'pergunta': None, 'sugestoes': SUGGESTIONS},
                    'eficiencia': {'hoje': {'media': 4200, 'locais': 3}, 'dias': []},
                    'trabalho': TRABALHO, 'foco': FOCO, 'presenca': {'batimento': __import__('time').time(), 'estado': 'ativo', 'microfone_aberto': True}}.get(name, {})
            body, kind = json.dumps(data).encode(), 'application/json'
        elif self.path in ['/config', '/props', '/stats', '/cerebros', '/orb'] or self.path.startswith('/tree'):
            data = CONFIG if self.path == '/config' else (
                {'name': 'Guia', 'notes': [{'title':'Primeiros passos','file':'0/guia.md'}], 'dirs': []}
                if self.path.startswith('/tree') else {'name':'Acervo','items':[], 'dirs':[{'name':'misc','items':['misc/burrinho_refeito_final.png','misc/porto_pe_final.png'],'dirs':[]}]})
            body, kind = json.dumps(data).encode(), 'application/json'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


async def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, passed = [], []
    with tempfile.TemporaryDirectory(prefix='jarvis-brain-browser-') as profile:
        process = subprocess.Popen([
            '/usr/bin/chromium', '--headless=new', '--remote-debugging-port=0',
            '--user-data-dir=' + profile, '--no-first-run', '--no-default-browser-check',
            '--window-size=1440,900', '--disable-background-networking',
            f'http://127.0.0.1:{server.server_port}/stage.html',
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            portfile = Path(profile) / 'DevToolsActivePort'
            for _ in range(100):
                if portfile.exists():
                    break
                await asyncio.sleep(.1)
            port = int(portfile.read_text().splitlines()[0])
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list', timeout=5) as response:
                pages = json.load(response)
            target = next(p for p in pages if p['type'] == 'page')
            async with websockets.connect(target['webSocketDebuggerUrl'], max_size=16_000_000) as ws:
                sequence = 0

                async def call(method, params=None):
                    nonlocal sequence
                    sequence += 1
                    await ws.send(json.dumps({'id': sequence, 'method': method, 'params': params or {}}))
                    while True:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), 10))
                        if msg.get('method') == 'Runtime.exceptionThrown':
                            errors.append(msg['params'])
                        if msg.get('id') == sequence:
                            assert 'error' not in msg, msg
                            return msg.get('result', {})

                async def ev(js):
                    result = await call('Runtime.evaluate', {'expression': '{' + js + '\n}', 'returnByValue': True, 'awaitPromise': True})
                    assert 'exceptionDetails' not in result, result
                    return result.get('result', {}).get('value')

                async def check(name, expression):
                    assert await ev(expression), name
                    passed.append(name)

                await call('Runtime.enable')
                for _ in range(50):
                    if await ev('window.stageReady === true'):
                        break
                    await asyncio.sleep(.1)
                await ev('''window.rect = selector => {
                    const el=document.querySelector(selector); const r=(el.querySelector('.hit') || el).getBoundingClientRect();
                    return {x:r.x+r.width/2,y:r.y+r.height/2};
                };
                window.tap = selector => { const p=rect(selector);
                    for(const type of ['pointerdown','pointerup']) document.elementFromPoint(p.x,p.y).dispatchEvent(
                      new PointerEvent(type,{bubbles:true,clientX:p.x,clientY:p.y,pointerId:1,button:0})); };
                window.hand = (id,x,y,pinched,cancelled=false) => window.jarvisBrainGestures.hand({id,x,y,pinched,cancelled});
                window.pinch = selector => {window.jarvisBrainGestures.finishFrame([]);const p=rect(selector); hand(0,p.x,p.y,false);hand(0,p.x,p.y,true);hand(0,p.x,p.y,false);};
                window.transform = () => document.querySelector('.mundo').getAttribute('transform');
                window.scale = () => document.querySelector('.mundo').transform.baseVal.getItem(1).matrix.a;
                ''')
                def row(node):
                    return f'[data-node="{node}"]'

                async def pinch_at(selector):
                    await ev(f"pinch({json.dumps(selector)})")

                await asyncio.sleep(.7)
                for _ in range(100):  # software WebGL: the avatar gives up and the ring returns
                    if await ev('!document.querySelector(".ringcard.jv-preparando")'):
                        break
                    await asyncio.sleep(.1)
                await check('without a GPU the flat ring comes back after the loading name', '''(() => {
                    const r = document.querySelector(".ringcard");
                    return !r.classList.contains("jv-preparando") && !r.classList.contains("jv-avatar")
                      && getComputedStyle(r.querySelector("canvas")).opacity === "1"; })()''')
                await check('original ring is the entry, without a fullscreen dashboard',
                            '!!document.querySelector(".ringcard canvas") && !jarvisBrainGestures.active && !document.querySelector("#jv-mapa .navegacao")')
                await ev('document.querySelector(".ringcard").click()')
                await asyncio.sleep(.7)
                await check('ring blooms the orbs of the Núcleo manifest',
                            '[...document.querySelectorAll(".card.orb h3")].map(e=>e.textContent).join(",")==="Mapa,Guia,Hoje,Trabalho,Acervo"')
                await check('orbital circles remain connected to the original ring',
                            'document.querySelectorAll("#jv-cabos path").length===5')
                await ev('window.savedCable=document.querySelector("#jv-cabos path");window.savedCableD=savedCable.getAttribute("d");jarvisItemDe(document.querySelector(".ringcard")).x+=30')
                await asyncio.sleep(.15)
                await check('moving the ring updates existing cables without rebuilding them',
                            'savedCable.isConnected && savedCable===document.querySelector("#jv-cabos path") && savedCable.getAttribute("d")!==savedCableD')
                await ev('stagePinch(\'[data-orb="brain"]\')')
                await asyncio.sleep(.4)
                await check('original stage pinch opens the brain expansion', 'jarvisBrainGestures.active')
                await check('the expansion leaves the original ring visible',
                            '''const a=document.querySelector(".ringcard").getBoundingClientRect(),b=document.querySelector("#jv-mapa").getBoundingClientRect();
                            b.left>a.right && b.width<innerWidth && document.querySelector("#jv-mapa").getAttribute("aria-modal")==="false"''')
                await check('three circular modes use the original glass language',
                            'document.querySelectorAll("#jv-mapa .modos button").length===3 && getComputedStyle(document.querySelector(".modos button")).borderRadius==="50%" && !document.querySelector("#jv-mapa .marca")')
                await check('brain circle connects to the neural board',
                            '!!document.querySelector(\'#jv-cabos [data-connection="workspace"]\')')
                await check('the Mapa has three areas around the Zé: Memória, Sessões, Automações',
                            '[...document.querySelectorAll(\'[data-node^="area:"]\')].map(e=>e.dataset.node).sort().join()==="area:automacoes,area:memoria,area:sessoes"')
                screenshot = await call('Page.captureScreenshot', {'format': 'png'})
                Path('/tmp/jarvis-original-brain.png').write_bytes(base64.b64decode(screenshot['data']))
                await ev('document.querySelector(\'[data-action="motion"]\').click()')
                await ev('const p=rect(\'[data-node="usuario:a"]\');hand(0,p.x,p.y,false)')
                await check('pointing previews the content and learning origin',
                            'document.querySelector(".previa").textContent.includes("Mostre as opções") && document.querySelector(".previa").style.display==="block"')
                await check('continuous pointing reuses the preview DOM', """(() => {
                    const preview=document.querySelector('.previa'), child=preview.firstChild;
                    const p=rect('[data-node="usuario:a"]');
                    for(let n=0;n<60;n++)hand(0,p.x+(n%2),p.y,false);
                    return child===preview.firstChild && preview.style.display==='block';
                })()""")
                await check('changing the pointed node updates the preview', """(() => {
                    const p=rect('[data-node="center"]');hand(0,p.x,p.y,false);
                    const preview=document.querySelector('.previa');
                    return preview.textContent.includes('Seu assistente') && !preview.textContent.includes('Mostre as opções');
                })()""")
                await ev('jarvisBrainGestures.finishFrame([]);const p=rect(".ringcard");window.outsideOwned=hand(0,p.x,p.y,false)')
                await check('hands outside the board remain available to the original ring', 'outsideOwned===false')
                await ev('jarvisBrainGestures.finishFrame([]);const p=rect(\'[data-node="usuario:a"]\');window.nodeBefore=document.querySelector(\'[data-node="usuario:a"]\').getAttribute("transform");window.before=transform();hand(0,p.x,p.y,true);hand(0,p.x+35,p.y+20,true);hand(0,p.x+35,p.y+20,false)')
                await check('pinch drag pulls a neural node, preserving the camera',
                            'document.querySelector(\'[data-node="usuario:a"]\').getAttribute("transform")!==nodeBefore && transform()===before')
                await ev('jarvisBrainGestures.finishFrame([]);const r=document.querySelector(".palco").getBoundingClientRect();window.bg={x:r.left+20,y:r.bottom-70};window.before=transform();hand(0,bg.x,bg.y,true);hand(0,bg.x+40,bg.y-30,true);hand(0,bg.x+40,bg.y-30,false)')
                await check('background pinch moves the connections board', 'transform()!==before')
                await ev('jarvisBrainGestures.finishFrame([]);document.querySelector(\'[data-action="fit"]\').click();const r=document.querySelector(".palco").getBoundingClientRect();window.beforeScale=scale();hand(0,r.left+30,r.bottom-80,true);hand(1,r.left+90,r.bottom-80,true);hand(0,r.left+10,r.bottom-80,true);hand(1,r.left+190,r.bottom-80,true);jarvisBrainGestures.finishFrame([])')
                await check('two accepted pinches enlarge the board', 'scale()>beforeScale*1.5')
                await ev('document.querySelector(\'[data-action="fit"]\').click();jarvisBrainGestures.finishFrame([]);const p=rect(\'[data-node="center"]\');window.radiusBefore=Number(document.querySelector(\'[data-node="center"] .bola\').getAttribute("r"));window.before=transform();hand(0,p.x-7,p.y,true);hand(1,p.x+7,p.y,true);hand(0,p.x-35,p.y,true);hand(1,p.x+35,p.y,true);jarvisBrainGestures.finishFrame([])')
                await check('two pinches on one sphere grow that sphere',
                            'Number(document.querySelector(\'[data-node="center"] .bola\').getAttribute("r"))>radiusBefore && transform()===before')
                await ev('jarvisBrainGestures.finishFrame([]);const r=document.querySelector("#jv-mapa").getBoundingClientRect();window.frameBefore=r.top;hand(0,r.left+160,r.top+20,true);hand(0,r.left+160,r.top+40,true);hand(0,r.left+160,r.top+40,false)')
                await check('the glass board can be dragged by its grip', 'document.querySelector("#jv-mapa").getBoundingClientRect().top>frameBefore')
                await ev('jarvisBrainGestures.finishFrame([]);const p=rect(\'[data-node="usuario:a"]\');hand(0,p.x,p.y,true);jarvisBrainGestures.finishFrame([])')
                await check('lost tracking cancels opening an item', 'document.querySelector("#jv-mapa").dataset.mode==="brain"')
                await ev('const p=rect(\'[data-node="usuario:a"]\');hand(0,p.x,p.y,true);hand(0,p.x,p.y,false,true)')
                await check('rejected pinch cannot open an item', 'document.querySelector("#jv-mapa").dataset.mode==="brain"')
                await pinch_at('[data-node="usuario:a"]')
                await check('pinch opens its item in Foco with the original correction',
                            'document.querySelector("#jv-mapa").dataset.mode==="focus" && document.querySelector(".focus-origem").textContent.includes("Mostre as opções")')
                await pinch_at('[data-action="mode:work"]')
                await check('Trabalho lists actual objects from the data contract',
                            'document.querySelectorAll(".work .objeto").length===2 && document.querySelector(".work").textContent.includes("Loja")')
                await pinch_at('[data-object="sessao:a"]')
                await check('a session opens in Foco with its last message',
                            'document.querySelector(".focus").textContent.includes("Testes passando") && document.querySelector(".focus h1").textContent==="Loja"')
                await pinch_at('[data-action="mode:work"]')
                await pinch_at('[data-action="area:memoria"]')
                await pinch_at('[data-object="usuario:b"]')
                await check('stored markup remains text in the selected object',
                            '!window.injected && !document.querySelector("#jv-mapa img") && document.querySelector(".focus-corpo").textContent.startsWith("<img")')
                await pinch_at('[data-action="mode:brain"]')
                await ev('jarvisBrainGestures.finishFrame([]);const p=rect(\'[data-node="usuario:a"]\');window.boardCalls=0;window.cur={x:p.x,y:p.y,pinched:true,history:[{x:p.x,y:p.y,t:10},{x:p.x,y:p.y,t:30}],probKill:false};feedTrackedHand(cur,0,false,30);cur.pinched=false;feedTrackedHand(cur,0,true,70)')
                await check('real stage routing consumes the pinch before board gestures',
                            'boardCalls===0 && document.querySelector("#jv-mapa").dataset.mode==="focus"')
                await ev('jarvisBrainGestures.finishFrame([]);const p=rect(".ringcard");window.boardCalls=0;feedTrackedHand({x:p.x,y:p.y,pinched:false,history:[],probKill:false},7,false,100)')
                await check('real stage routing lets outside hands reach original objects', 'boardCalls===1')
                await ev('document.querySelector(\'[data-action="mode:brain"]\').click()')
                await asyncio.sleep(.3)
                await ev('window.before=transform()')
                await asyncio.sleep(4.2)
                await check('refresh keeps the camera position', 'transform()===before')
                await call('Emulation.setDeviceMetricsOverride', {'width':800,'height':600,'deviceScaleFactor':1,'mobile':False})
                await asyncio.sleep(.4)
                await check('smaller windows retain the ring and all three circular modes',
                            '''const ring=document.querySelector(".ringcard").getBoundingClientRect();
                            ring.right<800 && [...document.querySelectorAll('.modos button,[data-action="close"]')].every(e=>{
                            const r=e.getBoundingClientRect();return r.left>=0&&r.top>=0&&r.right<=800&&r.bottom<=600;})''')
                screenshot = await call('Page.captureScreenshot', {'format': 'png'})
                Path('/tmp/jarvis-original-small.png').write_bytes(base64.b64decode(screenshot['data']))
                await call('Emulation.setEmulatedMedia', {'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
                await asyncio.sleep(.1)
                await check('reduced motion stops floating', 'document.querySelector(".mundo").dataset.motion==="paused"')
                await ev('jarvisBrainGestures.finishFrame([]);stagePinch(".ringcard")')
                await asyncio.sleep(.4)
                await check('original ring retracts the circles and the expansion together',
                            '!jarvisBrainGestures.active && document.querySelectorAll(".card.orb").length===0')
                await ev('stagePinch(".ringcard")')
                await asyncio.sleep(.6)
                await ev('stagePinch(\'[data-orb="1"]\')')
                await asyncio.sleep(.3)
                await check('Guia continues to open through the original file browser',
                            '!!document.querySelector(".panel.browser") && !jarvisBrainGestures.active')
                assert not errors, errors
                print(json.dumps({'passed': len(passed), 'checks': passed, 'browser_errors': errors, 'screenshot': '/tmp/jarvis-original-brain.png'}, ensure_ascii=False, indent=2))
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            server.shutdown()
            server.server_close()


def test_brain_navigation():
    asyncio.run(main())


if __name__ == '__main__':
    asyncio.run(main())
