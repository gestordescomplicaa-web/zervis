"""Hands calibrator, camera light and profile backup (no webcam, no real camera).

Run: python tests/test_maos.py   (or pytest tests/test_maos.py)
The browser part reuses the stage harness of test_brain_navigation.py and a
canvas stream in place of the camera; hand features are synthetic.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio
import json
import subprocess
import sys
import tempfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'jarvis' / 'imersivo' / 'web'  # a página
sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parent)]

import jarvis.imersivo.maos as jm  # noqa: E402

V4L2 = """User Controls

                     brightness 0x00980900 (int)    : min=0 max=255 step=1 default=128 value=73 flags=has-min-max
                           gain 0x00980913 (int)    : min=0 max=100 step=1 default=0 value=11 flags=has-min-max
        white_balance_automatic 0x0098090c (bool)   : default=1 value=1
                  auto_exposure 0x009a0901 (menu)   : min=0 max=3 default=3 value=3 (Aperture Priority Mode)
         exposure_time_absolute 0x009a0902 (int)    : min=1 max=5000 step=1 default=300 value=300 flags=inactive, has-min-max
                 focus_absolute 0x009a090a (int)    : min=0 max=1023 step=1 default=192 value=451 flags=inactive, has-min-max
"""
BOM = {'versao': 1, 'pincaFrontal': 0.36, 'pincaPerfil': 0.38, 'contraste': 0.15, 'arco': 1.3,
       'soltar': 0.5, 'soltarRapido': 0.65, 'tremor': 24, 'fantasma': 900, 'toqueMs': 420, 'toque3': 0.2}


class FakeV4l2:
    """v4l2-ctl stand-in: -l lists, -c name=value sets."""

    def __init__(self):
        self.ctl = jm.ler_controles(V4L2)
        self.chamadas = []

    def __call__(self, args):
        self.chamadas.append(args)
        if args[-1] == '-l':
            return '\n'.join(f'{k} 0x0 (int) : min={c["min"]} max={c["max"]} default={c["padrao"]} value={c["valor"]}'
                             for k, c in self.ctl.items())
        nome, valor = args[-1].split('=')
        self.ctl[nome]['valor'] = int(valor)
        return ''


def sysfs(tmp):
    for i, (nome, indice) in enumerate([('EMEET SmartCam S600: EMEET Smar', 0), ('EMEET SmartCam S600: EMEET Smar', 1)]):
        d = Path(tmp) / f'video{i}'
        d.mkdir()
        (d / 'name').write_text(nome + '\n')
        (d / 'index').write_text(f'{indice}\n')
    return Path(tmp)


def test_profile_keeps_the_default_as_the_way_back():
    with tempfile.TemporaryDirectory() as tmp:
        p = jm.Perfil(tmp)
        assert p.ler() == {'perfil': None, 'origem': 'padrao'}
        p.gravar(BOM, 'calibrado', {'toques': 5})
        assert p.ler()['perfil'] == BOM and p.ler()['origem'] == 'calibrado'
        p.gravar({**BOM, 'tremor': 27}, 'ajustado')
        assert json.loads((Path(tmp) / 'maos-perfil.anterior.json').read_text())['perfil'] == BOM
        p.padrao()
        assert p.ler()['origem'] == 'padrao' and (Path(tmp) / 'maos-perfil.anterior.json').exists()
        # Corrupt or out-of-bounds files fall back to the default, never crash.
        (Path(tmp) / 'maos-perfil.json').write_text('{"perfil": {"tremor": 999}}')
        assert p.ler()['perfil'] is None
        antigo = {k: v for k, v in BOM.items() if k != 'toque3'}
        (Path(tmp) / 'maos-perfil.json').write_text(json.dumps({'perfil': antigo, 'origem': 'calibrado'}))
        assert p.ler()['perfil'] == antigo  # saved before the 3D touch: still valid
        (Path(tmp) / 'maos-perfil.json').write_text('not json')
        assert p.ler()['perfil'] is None


def test_profile_bounds_are_enforced():
    assert jm.perfil_valido(BOM)
    for chave, valor in [('tremor', 60), ('pincaFrontal', 0.5), ('contraste', True), ('toqueMs', '400')]:
        assert not jm.perfil_valido({**BOM, chave: valor}), chave
    assert not jm.perfil_valido({**BOM, 'soltar': 0.45, 'pincaFrontal': 0.40})  # release must stay above pinch
    assert not jm.perfil_valido({**BOM, 'extra': 1})
    try:
        jm.Perfil(tempfile.mkdtemp()).gravar({**BOM, 'tremor': 99}, 'calibrado')
        raise AssertionError('accepted an invalid profile')
    except ValueError:
        pass


def test_v4l2_parsing_and_device_match():
    c = jm.ler_controles(V4L2)
    assert c['gain'] == {'valor': 11, 'min': 0, 'max': 100, 'padrao': 0}
    assert c['auto_exposure']['valor'] == 3 and c['white_balance_automatic']['max'] == 1
    with tempfile.TemporaryDirectory() as tmp:
        raiz = sysfs(tmp)
        assert jm.dispositivo_por_nome('EMEET SmartCam S600: EMEET Smar (328f:2013)', raiz) == ('/dev/video0', 'EMEET SmartCam S600: EMEET Smar')
        assert jm.dispositivo_por_nome('Outra câmera', raiz) == (None, None)


def test_camera_backs_up_originals_once_and_restores():
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as sys_tmp:
        raiz = sysfs(sys_tmp)
        fake = FakeV4l2()
        original = jm.dispositivo_por_nome
        jm.dispositivo_por_nome = lambda nome, r=raiz: original(nome, r)
        try:
            cam = jm.Camera(tmp, executar=fake, v4l2='/usr/bin/v4l2-ctl')
            nome = 'EMEET SmartCam S600: EMEET Smar (328f:2013)'
            info = cam.info(nome)
            assert info['disponivel'] and 'focus_absolute' not in info['controles']
            cam.ajustar(nome, {'gain': 40, 'auto_exposure': 1, 'exposure_time_absolute': 100})
            sets = [a[-1] for a in fake.chamadas if a[-2] == '-c']
            assert sets[0] == 'auto_exposure=1'  # manual mode before the exposure time
            backup = json.loads((Path(tmp) / 'camera-original.json').read_text())
            assert backup['EMEET SmartCam S600: EMEET Smar']['gain'] == 11
            cam.ajustar(nome, {'gain': 70})
            backup = json.loads((Path(tmp) / 'camera-original.json').read_text())
            assert backup['EMEET SmartCam S600: EMEET Smar']['gain'] == 11  # written once
            for ruim in ({'gain': 101}, {'focus_absolute': 10}, {'gain': '5'}, {'gain': True}):
                try:
                    cam.ajustar(nome, ruim)
                    raise AssertionError(f'accepted {ruim}')
                except ValueError:
                    pass
            cam.batimento = 0  # the watchdog's condition: tracker page stopped
            assert cam.alterada
            cam.restaurar()
            assert fake.ctl['gain']['valor'] == 11 and fake.ctl['auto_exposure']['valor'] == 3
            assert fake.ctl['exposure_time_absolute']['valor'] == 300 and not cam.alterada
        finally:
            jm.dispositivo_por_nome = original


# ---------- browser: guided calibration with a synthetic hand ---------------------
def browser_handler():
    import test_brain_navigation as tb

    perfil = jm.Perfil(tempfile.mkdtemp(prefix='maos-perfil-'))
    estado = {'diagnostico': None, 'ajustes': [], 'restaurado': 0, 'cerebro': None}

    class Handler(tb.Handler):
        def _json(self, obj):
            body = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/jarvis-maos.js':
                body = (ROOT / 'jarvis-maos.js').read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/javascript')
                self.end_headers()
                self.wfile.write(body)
            elif self.path == '/maos/perfil':
                self._json(perfil.ler())
            elif self.path == '/cerebros':
                # Same shape as the real state/cerebros.json (brain batteries).
                self._json({'lista': [
                    {'id': 'claude', 'nome': 'Claude', 'modelo': 'Sonnet 5.5', 'ativo': False,
                     'bateria': {'restante': 56, 'janela': 'semana', 'detalhe': ['semana: 56%']}},
                    {'id': 'gemini', 'nome': 'Gemini', 'modelo': 'Gemini 3.1 Pro', 'ativo': True,
                     'bateria': {'restante': 71, 'janela': '5 h', 'detalhe': []}},
                    {'id': 'auto', 'nome': 'Automático', 'modelo': None, 'ativo': False, 'bateria': None}]})
            elif self.path.startswith('/camera/info'):
                self._json({'disponivel': True, 'nome': 'fake', 'controles': {
                    'gain': {'valor': 11, 'min': 0, 'max': 100, 'padrao': 0},
                    'auto_exposure': {'valor': 3, 'min': 0, 'max': 3, 'padrao': 3},
                    'exposure_time_absolute': {'valor': 300, 'min': 1, 'max': 5000, 'padrao': 300},
                    'brightness': {'valor': 73, 'min': 0, 'max': 255, 'padrao': 128}}})
            else:
                super().do_GET()

        def do_POST(self):
            d = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert self.headers['Content-Type'] == 'application/json'
            if self.path == '/maos/perfil':
                if not d.get('padrao') and estado.get('salvar_liberado'):
                    assert estado['salvar_liberado'].wait(10), 'save was not released by the test'
                perfil.padrao() if d.get('padrao') else perfil.gravar(d['perfil'], d['origem'], d.get('resumo'))
                self._json(perfil.ler())
            elif self.path == '/cerebro':
                estado['cerebro'] = d.get('id')
                self._json({})
            elif self.path == '/camera/ajustar':
                estado['ajustes'].append(d['valores'])
                self._json({})
            elif self.path == '/camera/restaurar':
                estado['restaurado'] += 1
                self._json({})
            else:
                estado['diagnostico'] = d
                self._json({})

    return Handler, perfil, estado


# Synthetic hand. Open: wide gap, no index/back contrast. Pinch: the gap
# closes to 0.34 (just above the original 0.32 ceiling, so the default misses
# it) with a clear OK-sign. Fist: small gap, back fingers folded.
HAND = '''
window.maoFalsa = (() => {
  const cam = document.getElementById('cam'), tela = document.createElement('canvas');
  tela.width = 320; tela.height = 180; const g = tela.getContext('2d');
  window.cinzaFalso = [42, 90];
  const pintar = () => { const [f, m] = window.cinzaFalso; g.fillStyle = `rgb(${f},${f},${f})`; g.fillRect(0, 0, 320, 180);
    g.fillStyle = `rgb(${m},${m},${m})`; g.fillRect(120, 50, 80, 80); };
  pintar(); cam.srcObject = tela.captureStream(30); cam.play();
  setInterval(pintar, 33);
  let t0 = performance.now(), parado = false;
  const aberta = {ratio:.9, ratio3:.9, f8v:1.9, backMean:1.9, aspect:2.5, tRel:.5};
  const pinca = {ratio:.34, ratio3:.12, f8v:1.25, backMean:1.55, aspect:2.5, tRel:.5};
  // Almost touching: overlapped in the picture (2D gap under the ceiling, OK
  // sign) but apart in depth. The original counts it; the calibration must not.
  const quase = {ratio:.30, ratio3:.30, f8v:1.25, backMean:1.55, aspect:2.5, tRel:.5};
  const punho = {ratio:.30, ratio3:.35, f8v:1.12, backMean:1.12, aspect:2.5, tRel:.5};
  setInterval(() => {
    if (parado) return;
    const now = performance.now(), m = window.jarvisMaos, fase = m.estado().fase;
    let f = aberta;
    if (fase === 'toques') f = ((now - t0) % 900) < 240 ? pinca : aberta;
    else if (fase === 'punho') f = punho;
    else if (fase === 'quase') f = quase;
    const tremor = Math.sin(now / 70) * 2;
    m.amostra(0, {...f, okBack:false, pinched:false, x:720 + tremor + (f === pinca ? 6 : 0), y:420 + tremor, hspd:0, now,
      caixa:[.35,.3,.6,.75]});
  }, 33);
  return { parar() { parado = true; } };
})();
'''


async def calibrar_no_navegador():
    import test_brain_navigation as tb
    import websockets

    Handler, perfil, estado = browser_handler()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, passed = [], []
    with tempfile.TemporaryDirectory(prefix='jarvis-maos-browser-') as profile:
        process = subprocess.Popen([
            '/usr/bin/chromium', '--headless=new', '--remote-debugging-port=0',
            '--user-data-dir=' + profile, '--no-first-run', '--window-size=1440,900',
            '--disable-background-networking', '--autoplay-policy=no-user-gesture-required',
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
                target = next(p for p in json.load(response) if p['type'] == 'page')
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

                await call('Runtime.enable')
                for _ in range(80):
                    if await ev('window.stageReady === true && !!window.jarvisMaos'):
                        break
                    await asyncio.sleep(.1)
                await check('starts on the original profile', 'jarvisMaos.origem==="padrao" && jarvisMaos.p===jarvisMaos.PADRAO && jarvisMaos.p.pincaFrontal===0.32')
                await ev(HAND)
                await asyncio.sleep(1.5)
                await check('the HUD chip shows camera, light and profile', '/MÃOS · (\\d+|—) QPS · LUZ .+ · PADRÃO/.test(document.querySelector("#hud-maos .jv").textContent)')

                # Brightness filter the person turns on: the camera aims higher AND
                # a gentle picture filter; B steps it, Shift+B steps back.
                await check('brightness and theme chips sit next to the hands chip',
                            'document.querySelector("#hud-maos [data-acao=brilho]").textContent==="☀ BRILHO DESLIGADO" && document.querySelector("#hud-maos [data-acao=tema]").textContent==="◐ ORIGINAL"')
                await ev('document.querySelector("#hud-maos [data-acao=brilho]").click()')
                await check('a tap turns the brightness filter on', 'document.getElementById("cam").style.filter.includes("brightness(1.1") && jarvisMaos.brilho==="SUAVE" && localStorage.getItem("jv-brilho")==="1"')
                await check('and asks the camera itself for more light', 'jarvisMaos.estado().modoLuz==="ajustando"')
                await call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'b', 'code': 'KeyB'})
                await call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'b', 'code': 'KeyB'})
                await check('B steps up to strong', 'jarvisMaos.brilho==="FORTE" && document.getElementById("cam").style.filter.includes("brightness(1.35)")')
                await ev('jarvisMaos.mudarBrilho(0)')
                await check('off means the untouched picture', 'document.getElementById("cam").style.filter==="" && jarvisMaos.brilho==="DESLIGADO"')

                # The front shows only the ring and CPU/RAM/GPU/VRAM; the rest lives in D.
                await asyncio.sleep(1.2)
                await check('the front keeps only the CPU · RAM · GPU · VRAM row',
                            '[...document.querySelectorAll("#hint > .linha")].map(e=>e.id).join()==="hud-m"')
                await check('the settings menu starts closed', 'document.getElementById("jv-config").hidden')
                await call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'd', 'code': 'KeyD'})
                await check('D opens the settings menu with hands, brightness, colours, brains and usage',
                            '''!document.getElementById("jv-config").hidden && ["hud-maos","hud-c","hud-jv"].every(id=>document.getElementById(id).closest("#jv-config"))
                            && document.querySelector("#jv-config [data-config='brilho:0']").classList.contains("ativo")
                            && document.querySelector("#jv-config [data-config='tema:original']").classList.contains("ativo")''')
                await ev('document.querySelector("#jv-config [data-config=\'brilho:2\']").click()')
                await check('menu: brightness level by tap', 'jarvisMaos.brilho==="MÉDIO" && document.querySelector("#jv-config [data-config=\'brilho:2\']").classList.contains("ativo")')
                await ev('''window.jarvisBrainGestures.finishFrame([]);
                    const r=document.querySelector("#jv-config [data-config='brilho:0']").getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;
                    jarvisBrainGestures.hand({id:0,x,y,pinched:false});jarvisBrainGestures.hand({id:0,x,y,pinched:true});jarvisBrainGestures.hand({id:0,x,y,pinched:false});''')
                await check('menu: a hand pinch works too', 'jarvisMaos.brilho==="DESLIGADO"')
                await check('the menu is a side bar under the gear (top-left), shortcuts first', '''(()=>{const r=document.getElementById("jv-config").getBoundingClientRect(),g=document.getElementById("jv-engrenagem").getBoundingClientRect();
                    return g.left<30 && g.top<30 && r.left<30 && r.top>=g.bottom && r.width<=380 && r.height>innerHeight*0.6
                      && document.querySelector("#jv-config .corpo section h3").textContent==="Atalhos";})()''')
                await check('brain batteries keep their HUD look inside the menu', '''(()=>{const c=document.querySelector("#jv-config #hud-c .cer");
                    return !!c && getComputedStyle(c).borderRadius==="12px" && getComputedStyle(c).display==="flex" && !!c.querySelector(".b i")
                    && document.querySelectorAll("#jv-config #hud-c .cer").length===3 && document.querySelector("#jv-config #hud-c .cer.ativo").dataset.id==="gemini";})()''')
                await check('token usage shows inside the menu', '/TOKENS\\/RESPOSTA.*4,2 mil/.test(document.querySelector("#jv-config #hud-jv").textContent)')
                await ev('document.querySelector("#jv-config .cer[data-id=claude]").click()')
                await asyncio.sleep(.3)
                assert estado['cerebro'] == 'claude', estado['cerebro']
                passed.append('a tap on a brain in the menu switches the main brain')
                estado['cerebro'] = None
                await ev('''window.jarvisBrainGestures.finishFrame([]);
                    document.querySelector("#jv-config .cer[data-id=auto]").scrollIntoView({block:"center"});
                    const r=document.querySelector("#jv-config .cer[data-id=auto]").getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;
                    jarvisBrainGestures.hand({id:0,x,y,pinched:false});jarvisBrainGestures.hand({id:0,x,y,pinched:true});jarvisBrainGestures.hand({id:0,x,y,pinched:false});''')
                await asyncio.sleep(.3)
                assert estado['cerebro'] == 'auto', estado['cerebro']
                passed.append('and a hand pinch on a brain does it too')
                await call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Escape', 'code': 'Escape'})
                await check('Esc closes the menu', 'document.getElementById("jv-config").hidden')
                await call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'D', 'code': 'KeyD', 'modifiers': 8})
                await check('Shift+D still shows the debug readout, not the menu', 'document.getElementById("jv-config").hidden && document.getElementById("debug").style.display==="block"')
                await call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'D', 'code': 'KeyD', 'modifiers': 8})
                await check('the front carries the new name', 'document.title==="Zé · gdautomacao.ia" && !document.documentElement.outerHTML.includes("jaredrhod")')

                # Purple theme for light screens: CSS variables, the ring canvas and the graph.
                await ev('document.querySelector("#hud-maos [data-acao=tema]").click()')
                await check('a tap switches to the purple theme', '''document.body.classList.contains("tema-roxo") && localStorage.getItem("jv-tema")==="roxo"
                    && getComputedStyle(document.body).getPropertyValue("--jv-borda-rgb").trim()==="150 115 245"
                    && JSON.stringify(jarvisRing.COLS.idle)==="[109,40,217]" && JarvisGraph.CORES.root==="#a78bfa"''')
                await check('purple stays see-through glass, a step denser for light rooms', '''getComputedStyle(document.body).getPropertyValue("--jv-vidro-a").includes(".44")
                    && getComputedStyle(document.body).getPropertyValue("--jv-vidro-b").includes(".36")''')
                # T cycles every theme; each one recolours CSS, the ring and the graph,
                # and only one theme class is ever on.
                for nome, borda, anel in [('marinho', '96 146 240', '[37,99,235]'), ('esmeralda', '70 196 138', '[16,160,104]'),
                                          ('grafite', '168 176 190', '[120,128,145]')]:
                    await call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 't', 'code': 'KeyT'})
                    await check(f'T moves on to {nome}', f'''jarvisTema.nome==="{nome}" && document.body.classList.contains("tema-ativo")
                        && [...document.body.classList].filter(c=>c.startsWith("tema-")&&c!=="tema-ativo").join()==="tema-{nome}"
                        && getComputedStyle(document.body).getPropertyValue("--jv-borda-rgb").trim()==="{borda}"
                        && JSON.stringify(jarvisRing.COLS.idle)==="{anel}"''')
                await check('the menu offers all five themes', '''[...document.querySelectorAll("#jv-config [data-grupo=tema] button")].map(b=>b.textContent).join()==="Original,Roxo,Marinho,Esmeralda,Grafite"''')
                await call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 't', 'code': 'KeyT'})
                await check('T brings back the original colours exactly', '''!document.body.classList.contains("tema-ativo") && ![...document.body.classList].some(c=>c.startsWith("tema-"))
                    && getComputedStyle(document.body).getPropertyValue("--jv-borda-rgb").trim()==="140 240 225"
                    && JSON.stringify(jarvisRing.COLS.idle)==="[140,235,240]" && JarvisGraph.CORES.root==="#8ff0e4"''')
                assert estado['ajustes'], 'no camera adjustment sent'
                primeiro = estado['ajustes'][0]
                assert primeiro['auto_exposure'] == 1 and primeiro['exposure_time_absolute'] <= 133
                assert primeiro['brightness'] == 128
                await asyncio.sleep(1)
                assert max(a['exposure_time_absolute'] for a in estado['ajustes']) > primeiro['exposure_time_absolute']
                passed.append('the light steers the camera: manual short shutter, opened up on a dark room')
                # The room is now right: the light settles and then HOLDS, even with
                # small flicker and the hand coming and going.
                await ev('cinzaFalso=[120,124]')
                for _ in range(60):
                    if await ev('jarvisMaos.estado().modoLuz==="fixo"'):
                        break
                    await asyncio.sleep(.2)
                await check('the light settles to a fixed level', 'jarvisMaos.estado().modoLuz==="fixo"')
                await asyncio.sleep(.5)
                fixo, desde = json.dumps(estado['ajustes'][-1], sort_keys=True), len(estado['ajustes'])
                await ev('window.pisca=setInterval(()=>{cinzaFalso = cinzaFalso[0]===120 ? [112,150] : [120,124];}, 400)')
                await asyncio.sleep(3.5)
                await ev('clearInterval(pisca); cinzaFalso=[120,124]')
                assert all(json.dumps(a, sort_keys=True) == fixo for a in estado['ajustes'][desde:]), estado['ajustes'][desde:]
                assert await ev('jarvisMaos.estado().modoLuz==="fixo"')
                passed.append('then holds still through flicker and a hand coming and going')
                await ev('cinzaFalso=[25,40]')
                await asyncio.sleep(3)
                await check('a short change of the room does not move it', 'jarvisMaos.estado().modoLuz==="fixo"')
                await asyncio.sleep(3.5)
                await check('a lasting change makes it settle again', 'jarvisMaos.estado().modoLuz==="ajustando"')
                await check('no software lift while the camera can still add gain', 'jarvisMaos.estado().reforco===1 || jarvisMaos.estado().reforco<1.05')
                estado['salvar_liberado'] = threading.Event()
                await ev('document.querySelector("#hud-maos .btn").click()')
                await asyncio.sleep(.3)
                await check('the chip opens the guided calibration', '!document.getElementById("jv-calibra").hidden && jarvisMaos.calibrando')
                await check('while calibrating, the hand drives nothing else', 'jarvisMaos.amostra(0,{ratio:.9,f8v:1.9,backMean:1.9,aspect:2.5,tRel:.5,pinched:false,x:1,y:1,now:performance.now(),caixa:[.3,.3,.6,.7]})===true')
                for _ in range(900):   # ~25 s of steps; generous under machine load
                    if await ev('["salvando", "fim"].includes(jarvisMaos.estado().fase) || document.getElementById("jv-calibra").hidden'):
                        break
                    await asyncio.sleep(.1)
                await check('the result waits for the save and gestures remain suspended',
                            'jarvisMaos.estado().fase==="salvando" && jarvisMaos.calibrando && document.querySelector("#jv-calibra h2").textContent==="Salvando calibração"')
                assert perfil.ler()['origem'] != 'calibrado'
                estado['salvar_liberado'].set()
                for _ in range(100):
                    if await ev('jarvisMaos.estado().fase==="fim"'):
                        break
                    await asyncio.sleep(.1)
                texto = await ev('document.querySelector("#jv-calibra h2").textContent + " | " + document.querySelector("#jv-calibra .texto").textContent')
                await check('the calibration finishes with a result', 'jarvisMaos.estado().fase==="fim"')
                assert texto.startswith('Calibração pronta'), texto
                passed.append('result: ' + texto)
                await check('the new profile recognises the pinch the original missed', 'jarvisMaos.origem==="calibrado" && jarvisMaos.p.pincaFrontal>0.34 && jarvisMaos.p.pincaFrontal<=0.40')
                await check('never stricter than the original, inside the safe bounds', 'jarvisMaos.valido(jarvisMaos.p) && jarvisMaos.p.tremor>=12 && jarvisMaos.p.tremor<=48 && jarvisMaos.p.contraste<=0.18 && jarvisMaos.p.arco<=1.30 && jarvisMaos.p.pincaFrontal>=0.32')
                assert perfil.ler()['origem'] == 'calibrado'
                assert perfil.ler()['resumo']['reconhecidos'] == 5 and perfil.ler()['resumo']['reconhecidosPadrao'] == 0
                assert perfil.ler()['resumo']['punhosAceitos'] == 0
                assert perfil.ler()['resumo']['quasesPadrao'] == 3, perfil.ler()['resumo']
                assert perfil.ler()['resumo']['quasesAceitos'] == 0, perfil.ler()['resumo']
                await check('only a real touch clicks: the 3D line sits between touch and almost',
                            'jarvisMaos.p.toque3>0.12 && jarvisMaos.p.toque3<0.30')
                assert 'Quase encostar não conta mais' in texto, texto
                await call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Escape', 'code': 'Escape'})
                await check('Escape closes the result', 'document.getElementById("jv-calibra").hidden && !jarvisMaos.calibrando')

                # Daily refinement: three near-miss taps (moved a little), each
                # repeated at once on the same spot and then opened.
                antes = await ev('jarvisMaos.p.tremor')
                await ev('''for (let k = 0; k < 3; k++) {
                    jarvisMaos.registrar({resultado:"moveu", viagem: jarvisMaos.p.tremor + 4, dur: 200, x: 500, y: 300, alvo: true});
                    jarvisMaos.registrar({resultado:"abriu", viagem: 3, dur: 180, x: 505, y: 302, alvo: true}); }''')
                await asyncio.sleep(.5)
                await check('three near misses on the same spot widen the tolerance a little', f'jarvisMaos.p.tremor==={antes}+3 && jarvisMaos.origem==="ajustado"')
                assert perfil.ler()['resumo']['ajuste']['campo'] == 'tremor'
                await check('a lone drag is not evidence', f'''jarvisMaos.registrar({{resultado:"moveu",viagem:200,dur:900,x:10,y:10,alvo:true}});
                    jarvisMaos.registrar({{resultado:"abriu",viagem:2,dur:150,x:12,y:10,alvo:true}}); jarvisMaos.p.tremor==={antes}+3''')

                # The way back: Shift+K restores the original profile and camera.
                await call('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'K', 'code': 'KeyK', 'modifiers': 8})
                await asyncio.sleep(.5)
                await check('Shift+K brings back the original profile', 'jarvisMaos.origem==="padrao" && jarvisMaos.p===jarvisMaos.PADRAO')
                assert perfil.ler()['origem'] == 'padrao' and estado['restaurado'] >= 1
                n = len(estado['ajustes'])
                await asyncio.sleep(1.5)
                assert len(estado['ajustes']) == n, 'light kept steering the camera after the way back'
                passed.append('the light stops touching the camera after the way back')

                await ev('maoFalsa.parar()')
                await check('a missing profile file means the original', 'jarvisMaos.valido(jarvisMaos.PADRAO) && !jarvisMaos.valido({...jarvisMaos.PADRAO, tremor: 99})')
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


def test_guided_calibration_in_the_browser():
    asyncio.run(calibrar_no_navegador())


if __name__ == '__main__':
    for nome, fn in list(globals().items()):
        if nome.startswith('test_') and callable(fn):
            fn()
            print('ok', nome)
