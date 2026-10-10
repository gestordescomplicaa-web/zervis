"""Hand target sizes, reading zoom and shared folder/note controls in real Chromium."""
# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio
import base64
import json
import subprocess
import tempfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
import test_brain_navigation as tb

class Handler(tb.Handler):
    focus=json.loads(json.dumps(tb.FOCO))
    def do_GET(self):
        if self.path.startswith('/stage.html'):
            body=tb.HARNESS.replace('window.stageReady=true;', '''
              window.makeTestModel=()=>{const saved=buildModelScene;buildModelScene=async()=>null;
                const m=makeModel('/fixture.glb','Modelo');buildModelScene=saved;items.push(m);return m;};
              window.testGrab=beginGrab;window.testRelease=endGrab;
              window.stageReady=true;''').encode()
        elif self.path == '/jarvis/foco':
            body=json.dumps(self.focus).encode()
        elif self.path.startswith('/note?'):
            body=('Texto de leitura longo.\n' * 120).encode()
        elif self.path == '/config':
            body=json.dumps({**tb.CONFIG,'orbs':tb.CONFIG['orbs']+[{'id':'nova','title':'Nova orbe','kind':'notes'}]}).encode()
        else:
            return super().do_GET()
        self.send_response(200)
        self.send_header('Content-Type','text/html' if self.path.startswith('/stage.html') else 'application/json' if self.path=='/config' else 'text/plain')
        self.end_headers()
        self.wfile.write(body)

async def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, passed = [], []
    with tempfile.TemporaryDirectory(prefix='jarvis-interacao-', ignore_cleanup_errors=True) as profile:
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
                    result=await ev(js)
                    if not result:
                        print(await ev("[...document.querySelectorAll('.panel button')].map(e=>({text:e.textContent,r:e.getBoundingClientRect().toJSON()}))"),flush=True)
                    assert result, name
                    passed.append(name)

                await call('Runtime.enable')
                for _ in range(150):
                    if await ev('window.stageReady === true && !!window.jarvisCerebro'):
                        break
                    await asyncio.sleep(.1)
                await ev("""window.postsFoco=[];const f=window.fetch;window.fetch=(u,o)=>{
                  if(u==='/foco'){postsFoco.push(JSON.parse(o.body));return Promise.resolve(new Response('{"ok":true}'));}
                  return f(u,o);};
                  window.rect=s=>{const e=document.querySelector(s);const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};};
                  window.h=(id,x,y,pinched,cancelled=false)=>jarvisBrainGestures.hand({id,x,y,pinched,cancelled});
                  window.pinch=s=>{jarvisBrainGestures.finishFrame([]);const p=rect(s);h(0,p.x,p.y,false);h(0,p.x,p.y,true);h(0,p.x,p.y,false);};
                """)
                await ev('jarvisCerebro.mostrarFoco()')
                for _ in range(80):
                    if await ev("document.querySelector('#jv-mapa').classList.contains('on') && new DOMMatrix(getComputedStyle(document.querySelector('#jv-mapa')).transform).a>.999"):
                        break
                    await asyncio.sleep(.1)
                await check('Foco has reachable large zoom and close controls', """[...document.querySelectorAll('#jv-mapa .grip button,#jv-mapa .ferramentas button:not([hidden])')].every(e=>{
                  const r=e.getBoundingClientRect();return r.width>=55&&r.height>=55&&r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight;})""")
                await ev("""window.heldButton=document.querySelector('.foco-v');const p=rect('.foco-v');h(0,p.x,p.y,true);""")
                Handler.focus['atual']['titulo']='Atualizado pela voz'
                await asyncio.sleep(.85)
                await check('voice refresh cannot replace the button under a held pinch', 'heldButton.isConnected')
                await ev('jarvisBrainGestures.finishFrame([])')
                for _ in range(30):
                    if await ev("document.querySelector('.focus').textContent.includes('Atualizado pela voz')"):
                        break
                    await asyncio.sleep(.1)
                await check('pending Foco data appears after the hand releases', "document.querySelector('.focus').textContent.includes('Atualizado pela voz')&&postsFoco.length===0")
                # Two simultaneous pinches over actionable content must zoom, never submit.
                await ev("""const p=rect('.foco-cartao.atual .foco-v');window.origin=p;
                  h(0,p.x-50,p.y,true);h(1,p.x+50,p.y,true);h(0,p.x-80,p.y,true);h(1,p.x+80,p.y,true);
                  h(0,p.x-80,p.y,false);h(1,p.x+80,p.y,false);jarvisBrainGestures.finishFrame([]);""")
                await check('two hands enlarge Foco without marking a task', "jarvisCerebro.estado().modo==='foco'&&jarvisCerebro.estado().zoom>=150&&postsFoco.length===0")
                await ev("pinch('[data-action=\"zoom-out\"]')")
                await check('pinching minus reduces Foco in place', "jarvisCerebro.estado().zoom<150&&jarvisCerebro.estado().modo==='foco'")
                await ev("pinch('[data-action=\"fit\"]')")
                await check('fit restores readable default size', 'jarvisCerebro.estado().zoom===100')
                await ev("""const p=rect('.foco-cartao.atual .foco-v');h(0,p.x,p.y,true);h(0,p.x,p.y-90,true);h(0,p.x,p.y-90,false);""")
                await check('one pinch scrolls content without activating its button', "document.querySelector('.focus').scrollTop>0&&postsFoco.length===0")
                await ev("jarvisBrainGestures.finishFrame([]);jarvisCerebro.modo('trabalho');jarvisCerebro.zoom(1.5)")
                await check('voice/API zoom retains Work and its own reading scale', "jarvisCerebro.estado().modo==='trabalho'&&jarvisCerebro.estado().zoom===150")
                await ev("jarvisCerebro.modo('foco')")
                await check('each reading mode keeps its own size', 'jarvisCerebro.estado().zoom===100')
                await ev("document.querySelector('.focus').scrollTop=0;pinch('[data-action=\"window-fit\"]')")
                await asyncio.sleep(.2)
                await check('window fit enlarges the frame within the display', "document.querySelector('#jv-mapa').getBoundingClientRect().width>=innerWidth-26")
                shot=await call('Page.captureScreenshot', {'format':'png'})
                Path('/tmp/jarvis-interacao-foco.png').write_bytes(base64.b64decode(shot['data']))
                await ev("pinch('[data-action=\"close\"]');jarvisStage.abrirNucleo()")
                await asyncio.sleep(.5)
                await ev("document.querySelector('[data-orb=\"5\"]').click()")
                await asyncio.sleep(.6)
                await check('a new manifest orb inherits the same panel controls', 'document.querySelectorAll(".panel .panel-tools button").length===4')
                await ev("window.pane=document.querySelector('.panel');window.it=jarvisItemDe(pane);window.oldScale=it.scale;pinch('.panel [data-panel-action=\"larger\"]')")
                await asyncio.sleep(.2)
                await check('hand zoom changes the panel without closing it', "it.scale>oldScale&&it.anim?.k!=='out'")
                await ev("pinch('.panel [data-panel-action=\"fit\"]')")
                await check('panel fit returns to default size', 'it.scale===1')
                await ev("""pinch('.panel [data-panel-action="smaller"]');pinch('.panel [data-panel-action="smaller"]');""")
                await asyncio.sleep(.2)
                await check('panel controls stay usable at the smallest scale', "[...pane.querySelectorAll('button')].every(e=>e.getBoundingClientRect().width>=54&&e.getBoundingClientRect().height>=54)")
                await ev("jarvisPanels.scale(it,2)")
                await asyncio.sleep(.2)
                await check('maximal panel zoom keeps every control on screen', "[...pane.querySelectorAll('button')].every(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight;})")
                await ev("jarvisPanels.scale(it,1)")
                await asyncio.sleep(.2)
                await ev("""const p=rect('.panel .bar h3'),cur={...p,history:[]};testGrab(it,91,cur);testRelease(it,91,cur);""")
                await check('a short hand pinch on the title does not close the panel', "it.anim?.k!=='out'")
                await ev("""document.querySelector('[data-orb="1"]').click()""")
                for _ in range(40):
                    if await ev("document.querySelectorAll('.panel').length===2"):
                        break
                    await asyncio.sleep(.1)
                await ev("""window.other=[...document.querySelectorAll('.panel')].find(e=>e!==pane);
                  const c=jarvisItemDe(other);jarvisPanels.prepare(c);c.x=it.x;c.y=it.y;
                  pane.parentElement.append(pane);""")
                await asyncio.sleep(.3)
                await check('the visible panel receives the hand when panels overlap', "stageHitTest(rect('.panel:last-child .bar h3'))===it")
                await ev('jarvisPanelActions.close(jarvisItemDe(other))')
                for _ in range(80):
                    if await ev('!other.isConnected'):
                        break
                    await asyncio.sleep(.1)
                # Use actual browser mouse events: no synthetic click shortcut.
                p=await ev("rect('.panel .bar h3')")
                await call('Input.dispatchMouseEvent',{'type':'mousePressed','x':p['x'],'y':p['y'],'button':'left','clickCount':1})
                await call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':p['x'],'y':p['y'],'button':'left','clickCount':1})
                await check('a click on the title no longer closes the panel', "it.anim?.k!=='out'")
                await call('Input.dispatchMouseEvent',{'type':'mousePressed','x':p['x'],'y':p['y'],'button':'left','clickCount':1})
                await call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':p['x']-70,'y':p['y']+30,'button':'left','buttons':1})
                await call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':p['x']-70,'y':p['y']+30,'button':'left','clickCount':1})
                await asyncio.sleep(.2)
                await check('mouse dragging the title moves the panel', "Math.abs(rect('.panel .bar h3').x-"+str(p['x'])+")>20")
                p=await ev("rect('.panel .brow')")
                await call('Input.dispatchMouseEvent',{'type':'mousePressed','x':p['x'],'y':p['y'],'button':'left','clickCount':1})
                await call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':p['x'],'y':p['y'],'button':'left','clickCount':1})
                await asyncio.sleep(.5)
                await check('mouse row click opens a note with the same controls', '!!document.querySelector(".panel:not(.browser) .panel-tools")')
                await ev("window.note=document.querySelector('.panel:not(.browser)');window.n=jarvisItemDe(note)")
                p=await ev("rect('.panel:not(.browser) .body')")
                await call('Input.dispatchMouseEvent',{'type':'mouseWheel','x':p['x'],'y':p['y'],'deltaX':0,'deltaY':250})
                await asyncio.sleep(.2)
                await check('mouse wheel scrolls the note', 'n.scrollY>0')
                await ev("""jarvisBrainGestures.finishFrame([]);const p=rect('.panel:not(.browser) [data-panel-action="close"]');h(0,p.x,p.y,true);h(0,p.x,p.y,false,true);""")
                await check('lost tracking on close leaves the note open', "n.anim?.k!=='out'")
                await ev("pinch('.panel:not(.browser) [data-panel-action=\"close\"]')")
                for _ in range(80):
                    if await ev('!note.isConnected'):
                        break
                    await asyncio.sleep(.1)
                await check('deliberate pinch closes the note', '!note.isConnected')
                await ev("window.model=makeTestModel();window.orbCount=document.querySelectorAll('.orb').length;model.el.click()")
                await check('clicking an Acervo model closes it instead of opening the avatar menu', "model.anim?.k==='out'&&document.querySelectorAll('.orb').length===orbCount")
                # Small viewport and enlarged reading must keep toolbar targets reachable.
                await call('Emulation.setDeviceMetricsOverride',{'width':800,'height':600,'deviceScaleFactor':1,'mobile':False})
                await ev("jarvisCerebro.mostrarFoco();jarvisConfig.abrir()")
                await asyncio.sleep(.3)
                await check('settings choices and close have generous hit areas', "[...document.querySelectorAll('#jv-config button')].every(e=>{const r=e.getBoundingClientRect();return r.width>=54&&r.height>=54;})")
                await ev("""jarvisBrainGestures.finishFrame([]);const r=document.querySelector('#jv-config').getBoundingClientRect();
                  h(0,r.left+80,r.top+240,true);h(0,r.left+80,r.top+120,true);h(0,r.left+80,r.top+120,false);""")
                await check('a hand can scroll the larger settings choices', "document.querySelector('#jv-config .corpo').scrollTop>0")
                await ev('jarvisConfig.fechar();jarvisCerebro.zoom(2)')
                await asyncio.sleep(.3)
                await check('Foco zoom keeps its close and zoom toolbar accessible on a smaller screen', "[...document.querySelectorAll('#jv-mapa .grip button,#jv-mapa .ferramentas button:not([hidden])')].every(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight;})")
                shot=await call('Page.captureScreenshot', {'format':'png'})
                Path('/tmp/jarvis-interacao-pequena.png').write_bytes(base64.b64decode(shot['data']))
                assert not errors,errors
                print(json.dumps({'passed':len(passed),'checks':passed},ensure_ascii=False,indent=2))
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            server.shutdown()
            server.server_close()


def test_interacao():
    asyncio.run(main())

if __name__ == '__main__':
    asyncio.run(main())
