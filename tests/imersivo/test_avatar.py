"""The avatar: the Zé's holographic chimpanzee (Blender glTF) inside the ring
widget (a tap only pulses him: no Núcleo orbs since 29/10/2026), switchable back to the ring from the D menu, by the
Zé (action visual) or by voice.

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
    with tempfile.TemporaryDirectory(prefix='jarvis-avatar-', ignore_cleanup_errors=True) as profile:
        process = subprocess.Popen([
            '/usr/bin/chromium', '--headless=new', '--remote-debugging-port=0', '--user-data-dir=' + profile,
            '--no-first-run', '--window-size=1440,900', '--disable-background-networking',
            '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
            f'http://127.0.0.1:{server.server_port}/stage.html?avatar=forcar',
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
                    if await ev('window.stageReady === true && window.jarvisAvatar?.montados === 1'):
                        break
                    await asyncio.sleep(.1)
                await check('the ring widget wears the 3D chimpanzee over the hidden ring drawing', '''(() => {
                    const r = document.querySelector(".ringcard"), c = r.querySelector("canvas.jv-avatar-cena");
                    return r.classList.contains("jv-avatar") && c && c.width > 0 && !r.classList.contains("jv-preparando")
                      && getComputedStyle(r.querySelector("canvas")).opacity === "0"; })()''')
                await ev("""window.flatDraws=0;
                    const ctx=document.querySelector('.ringcard > canvas').getContext('2d');
                    const clear=ctx.clearRect.bind(ctx);ctx.clearRect=(...args)=>{flatDraws++;clear(...args);};""")
                await asyncio.sleep(.3)
                await check('the hidden flat canvas does no drawing behind the avatar', 'flatDraws===0')
                await ev('jarvisAvatar.usar(false)')
                await asyncio.sleep(.3)
                await check('switching back resumes the flat ring drawing', 'flatDraws>0')
                await ev('jarvisAvatar.usar(true)')
                for _ in range(100):
                    if await ev('jarvisAvatar.montados===1'):
                        break
                    await asyncio.sleep(.1)
                await asyncio.sleep(1)
                shot = await call('Page.captureScreenshot', {'format': 'png'})
                Path('/tmp/jarvis-chimpanze-atual.png').write_bytes(base64.b64decode(shot['data']))
                await check('the Blender chimpanzee with its mouth and blink shape keys, mouth closed', '''(() => {
                    const d=jarvisAvatar.diagnostico()[0];return d.modelo==='chimpanze'&&d.expressoes.includes('Boca_Aberta')
                      &&d.expressoes.includes('Piscar')&&d.bocaAberta<.01;
                })()''')
                # Feed the real ring wave path; no alternate animation implementation.
                await ev('window.avatarFeed=setInterval(()=>{jarvisRing.data={state:"speaking",wave:Array(64).fill(.6)};},20)')
                for _ in range(50):
                    if await ev('jarvisAvatar.diagnostico()[0].bocaAberta>.3'):
                        break
                    await asyncio.sleep(.1)
                await check('the played speech waveform opens the mouth shape key', 'jarvisAvatar.diagnostico()[0].bocaAberta>.3')
                shot = await call('Page.captureScreenshot', {'format': 'png'})
                Path('/tmp/jarvis-chimpanze-falando.png').write_bytes(base64.b64decode(shot['data']))
                await ev('clearInterval(avatarFeed);window.avatarFeed=setInterval(()=>{jarvisRing.data={state:"speaking",wave:Array(64).fill(0)};},20)')
                await asyncio.sleep(1.2)
                await check('silence during speech closes the mouth', 'jarvisAvatar.diagnostico()[0].boca<.025')
                await ev('clearInterval(avatarFeed);window.avatarFeed=setInterval(()=>{jarvisRing.data={state:"listening",wave:Array(64).fill(.9)};},20)')
                await asyncio.sleep(.4)
                await check('listening never animates speech even with a residual wave', 'jarvisAvatar.diagnostico()[0].boca<.01')
                await ev('clearInterval(avatarFeed);window.avatarFeed=setInterval(()=>{jarvisRing.data={state:"thinking",wave:null};},20)')
                await asyncio.sleep(.5)
                pulsos = []
                # Wait for an actual pulse swing; parallel software WebGL can
                # render fewer than eight frames during the old fixed 0.8 s window.
                for _ in range(80):
                    pulsos.append(await ev('jarvisAvatar.diagnostico()[0].pulso'))
                    if max(pulsos)-min(pulsos)>.2:
                        break
                    await asyncio.sleep(.1)
                assert max(pulsos) - min(pulsos) > .2, pulsos
                for _ in range(30):  # slow software frames: the face eases in
                    if await ev('jarvisAvatar.diagnostico()[0].olharCima>.4'):
                        break
                    await asyncio.sleep(.1)
                await check('thinking pulses and shows the pensive face (eyes up)', 'jarvisAvatar.diagnostico()[0].olharCima>.4')
                await ev('clearInterval(avatarFeed);jarvisRing.data={state:"idle",wave:null}')
                # Emotions: the Zé's controller action and the avatar API mix the new keys.
                async def ate(js):
                    for _ in range(60):
                        if await ev(js):
                            return
                        await asyncio.sleep(.1)
                # The hand's spin mode turns the Zé inside his 3D scene, not the flat card,
                # and released he settles back facing the user.
                await ev('(()=>{const it=jarvisItemDe(document.querySelector(".ringcard"));it.rx=.4;it.ry=2.2;it.rvy=0;it.mode="rotate";it.grabbedBy=[0];})()')
                await asyncio.sleep(.6)
                await check('spin mode turns the 3D Zé, the card stays flat', '''(() => {
                    const r = document.querySelector(".ringcard"), d = jarvisAvatar.diagnostico()[0];
                    return Math.abs(d.giro - 2.2) < .05 && !/rotateY/.test(r.style.transform); })()''')
                await ev('(()=>{const it=jarvisItemDe(document.querySelector(".ringcard"));it.ry=.8;it.grabbedBy=[];it.mode=null;})()')
                for _ in range(120):  # slow software frames under the parallel suite
                    if await ev('Math.abs(jarvisAvatar.diagnostico()[0].giro - 2*Math.PI) < .1 || Math.abs(jarvisAvatar.diagnostico()[0].giro) < .1'):
                        break
                    await asyncio.sleep(.1)
                await check('released, he turns back to face the user', 'Math.abs(Math.cos(jarvisAvatar.diagnostico()[0].giro) - 1) < .02')
                # "Dê uma voltinha": the controller action spins him a full turn, ending facing front.
                await ev('jarvisControle.executar({id: "g1", acoes: [{acao: "girar", valor: 1}]})')
                await check('a little spin starts on command', 'jarvisAvatar.diagnostico()[0].girando')
                for _ in range(80):
                    if await ev('!jarvisAvatar.diagnostico()[0].girando'):
                        break
                    await asyncio.sleep(.1)
                await check('and ends one full turn later, facing front', '''(() => {
                    const g = jarvisAvatar.diagnostico()[0].giro; return Math.abs(g - 2*Math.PI) < .05 || Math.abs(g) < .05; })()''')
                # Spun round and round by hand, he gets dizzy and tells the Zé (once).
                await ev('''(()=>{window.eventos=[];const o=jarvisControle.evento;jarvisControle.evento=t=>{eventos.push(t);return o(t)};
                  const it=jarvisItemDe(document.querySelector(".ringcard"));it.grabbedBy=[0];it.mode="rotate";
                  window.rodar=setInterval(()=>{it.ry=(it.ry||0)+.35;},20);})()''')
                for _ in range(80):  # the event leaves in the frame he gets dizzy; the face, the next
                    if await ev('eventos.length > 0 && jarvisAvatar.diagnostico()[0].tonto > 0'):
                        break
                    await asyncio.sleep(.1)
                await check('spinning him too much makes him dizzy and he says so', '''(() => {
                    const d = jarvisAvatar.diagnostico()[0]; return d.tonto > 0 && eventos.length === 1 && eventos[0] === "tonto"; })()''')
                await ev('''(()=>{clearInterval(rodar);const it=jarvisItemDe(document.querySelector(".ringcard"));it.grabbedBy=[];it.mode=null;it.ry=0;})()''')
                await ev('jarvisControle.executar({id: "e1", acoes: [{acao: "expressao", valor: "alegria", segundos: 30}]})')
                await ate('jarvisAvatar.diagnostico()[0].sorriso>.6')
                await check('joy smiles showing the teeth (a key added in Blender)', '''(() => {
                    const d=jarvisAvatar.diagnostico()[0];return d.emocao==='alegria'&&d.sorriso>.6&&d.expressoes.includes('Sorriso_Dentes');})()''')
                await ev('jarvisAvatar.sentir("raiva", 30)')
                await ate('jarvisAvatar.diagnostico()[0].rosnar>.6')
                await check('anger replaces joy: the smile fades first, then the snarl', '''(() => {
                    const d=jarvisAvatar.diagnostico()[0];return d.emocao==='raiva'&&d.rosnar>.6&&d.sorriso<.2;})()''')
                await ev('jarvisAvatar.sentir("dúvida", 30)')
                await ate('jarvisAvatar.diagnostico()[0].duvida>.6')
                await check('doubt (spoken with the accent) raises one brow', 'jarvisAvatar.diagnostico()[0].emocao==="duvida"')
                await check('an unknown emotion is refused with the list', '''(() => {
                    try { jarvisAvatar.sentir("tédio"); return false; } catch (e) { return /alegria, duvida, raiva, tristeza/.test(e.message); } })()''')
                await ev('jarvisAvatar.sentir("tristeza", 30)')
                await ate('jarvisAvatar.diagnostico()[0].tristeza>.6')
                await check('sadness: inner brows up, mouth corners down (keys from the Blender script)', '''(() => {
                    const d=jarvisAvatar.diagnostico()[0];return d.emocao==='tristeza'&&d.tristeza>.6&&d.duvida<.2;})()''')
                await ev('jarvisAvatar.sentir("neutro")')
                await ate('jarvisAvatar.diagnostico()[0].tristeza<.05')
                await check('neutro brings the resting face back', '!jarvisAvatar.diagnostico()[0].emocao')
                n0 = await ev('jarvisAvatar.quadros')
                await asyncio.sleep(2)
                # Software WebGL is throttled to ~10 fps; the GPU path draws ~30.
                await check('it keeps drawing on its own', f'jarvisAvatar.quadros - {n0} >= 5')
                await ev('document.querySelector(".ringcard").click()')
                await asyncio.sleep(.8)
                await check('tapping it blooms no orbs (the Núcleo opens by name)', '!document.querySelector(".card.orb")')
                r = await ev('jarvisControle.executar({id: "v1", acoes: [{acao: "visual", valor: "anel"}]}).then(() => jarvisControle.estado())')
                await asyncio.sleep(.3)
                await check('the Zé can bring the ring back ("volta o anel")', '''!document.querySelector("canvas.jv-avatar-cena")
                    && !document.querySelector(".ringcard").classList.contains("jv-avatar")
                    && getComputedStyle(document.querySelector(".ringcard canvas")).opacity === "1" && jarvisControle.estado().visual === "anel"''')
                await ev('jarvisConfig.abrir()')
                await check('the D menu shows Visual: Avatar / Anel, Anel marked', '''document.querySelector("[data-config='visual:anel']").classList.contains("ativo")
                    && !document.querySelector("[data-config='visual:avatar']").classList.contains("ativo")''')
                await ev('document.querySelector("[data-config=\'visual:avatar\']").click()')
                for _ in range(100):
                    if await ev('window.jarvisAvatar.montados === 1'):
                        break
                    await asyncio.sleep(.1)
                await check('and the menu puts the avatar back, remembered for the next start', '''!!document.querySelector("canvas.jv-avatar-cena")
                    && localStorage.getItem("jv-visual") === "avatar" && document.querySelector("[data-config='visual:avatar']").classList.contains("ativo")''')
                await ev('jarvisConfig.alternar();stagePinch(".ringcard")')
                await asyncio.sleep(.7)
                await check('a pinch tap on the avatar is measured for the calibration and opens nothing',
                            '!document.querySelector(".card.orb") && !document.querySelector(".panel")')
                await ev('jarvisAvatar.usar(false);jarvisAvatar.usar(true);jarvisAvatar.usar(false);jarvisAvatar.usar(true)')
                await asyncio.sleep(.8)
                await check('rapid visual changes leave one live scene and one label', '''jarvisAvatar.montados===1
                    &&document.querySelectorAll('.jv-avatar-cena').length===1&&document.querySelectorAll('.jv-avatar-identidade').length===1''')
                # The presentation (ADR 0045): the Zé moves aside and his own data materializes as
                # real board items, linked to him by beams; encerrar brings everything back.
                antes = await ev('(()=>{const r=jarvisStage.anel();return {x:r.x,y:r.y};})()')
                await ev('jarvisApresentacao.ritmo=.03;jarvisControle.executar({id:"a1",acoes:[{acao:"apresentar",valor:"quem"}]})')
                cinco = '''(() => {
                    const els = [...document.querySelectorAll(".card.jv-holo")];
                    return els.length === 5 && els.every(el => jarvisItemDe(el)?.type === "holo")
                      && document.querySelectorAll("#jv-feixes .feixe").length === 5
                      && document.querySelector(".jv-holo h2").textContent === "Identidade"
                      && !!document.querySelector(".jv-holo .jv-grafo canvas"); })()'''
                for _ in range(150):  # slow software frames: the graph draws a moment after its panel
                    if await ev(cinco):
                        break
                    await asyncio.sleep(.1)
                await check('the presentation shows five panels from the self-knowledge, as board items', cinco)
                for _ in range(40):
                    if await ev('document.querySelector(".jv-heroi b").textContent === "6"'):
                        break
                    await asyncio.sleep(.1)
                await check('the numbers are the Zé\'s own (the sample: 6 requests)', 'document.querySelector(".jv-heroi b").textContent === "6"')
                await check('the Zé moved to the left, a caption tells what is shown', '''(() => {
                    const r = jarvisStage.anel(); return r.x < innerWidth * .3 && document.getElementById("jv-legenda-ze").textContent.length > 0; })()''')
                await ev('jarvisControle.executar({id:"a2",acoes:[{acao:"apresentar",valor:"encerrar"}]})')
                for _ in range(150):
                    if await ev(f'(()=>{{const r=jarvisStage.anel();return Math.abs(r.x-{antes["x"]})<3 && !document.querySelector(".card.jv-holo");}})()'):
                        break
                    await asyncio.sleep(.1)
                await check('encerrar clears the panels and the beams, and the Zé goes back', f'''(() => {{
                    const r = jarvisStage.anel(); return Math.abs(r.x - {antes["x"]}) < 3 && !document.querySelector(".card.jv-holo")
                      && !document.querySelector("#jv-feixes .feixe") && !jarvisApresentacao.apresentando; }})()''')
                # A scene the Zé writes (ADR 0047): cleaned on the page, unknown blocks dropped, numbers
                # without a source tagged ILUSTRATIVO, the blocks drawn on board items.
                cena = {'titulo': 'Teste', 'passos': [
                    {'fala': 'Um.', 'blocos': [{'tipo': 'titulo', 'texto': 'Teste'}, {'tipo': 'numero', 'valor': 42, 'unidade': 'm/s'}]},
                    {'fala': 'Dois.', 'blocos': [{'tipo': 'forma3d', 'forma': 'neural'}, {'tipo': 'barras', 'fonte': 'medição', 'itens': [{'nome': 'a', 'valor': 2}]},
                                                 {'tipo': 'video', 'url': 'x'}]}]}
                r = await ev(f'jarvisApresentacao.ritmo=.03;jarvisControle.executar({{id:"c1",acoes:[{{acao:"explicar",cena:{json.dumps(cena)}}}]}}).then(()=>1)')
                quatro = '''(() => { const els = [...document.querySelectorAll(".card.jv-holo.jv-cena")];
                    return els.length === 4 && els.every(el => jarvisItemDe(el)?.type === "holo")
                      && !!document.querySelector(".jv-cena-forma3d canvas") && !!document.querySelector(".jv-cena-titulo h1"); })()'''
                for _ in range(150):
                    if await ev(quatro):
                        break
                    await asyncio.sleep(.1)
                await check('a written scene becomes four drawn blocks on the board (the unknown one dropped)', quatro)
                await check('a number without a source says ILUSTRATIVO, one with a source says it, a scheme says ESQUEMA', '''(() => {
                    const f = t => document.querySelector(".jv-cena-" + t + " .jv-h-fonte").textContent;
                    return f("numero") === "ILUSTRATIVO" && f("barras") === "FONTE · MEDIÇÃO" && f("forma3d") === "ESQUEMA"; })()''')
                await check('the screen state names the running scene', '''(() => { const e = jarvisControle.estado();
                    return e.apresentacao.cena === "Teste" && e.apresentacao.ativa; })()''')
                await ev('jarvisApresentacao.encerrar()')
                await asyncio.sleep(.6)
                # The background (29/10/2026): the camera or the dark animated scene; the video only
                # shrinks out of sight, so the hands keep being tracked, and the choice is remembered.
                await ev('jarvisFundo.usar("escuro")')
                await asyncio.sleep(.5)
                await check('the dark background hides the camera image and draws its own scene', '''(() => {
                    const cam = document.getElementById("cam"), cena = document.getElementById("jv-fundo-cena");
                    return document.body.classList.contains("jv-escuro") && cam.getBoundingClientRect().width <= 2
                      && getComputedStyle(cena).display === "block" && cena.width > 0
                      && localStorage.getItem("jv-fundo") === "escuro"; })()''')
                await ev('jarvisConfig.abrir()')
                await check('the D menu marks Fundo: Escuro', 'document.querySelector("[data-config=\'fundo:escuro\']").classList.contains("ativo")')
                await ev('jarvisConfig.alternar();document.body.dispatchEvent(new KeyboardEvent("keydown",{key:"f",bubbles:true}))')
                await asyncio.sleep(.3)
                await check('F brings the camera back', '!document.body.classList.contains("jv-escuro") && jarvisFundo.modo === "camera"')
                await check('the constellation draws past the card, the card keeps its size', '''(() => {
                    const r = document.querySelector(".ringcard").getBoundingClientRect(), c = document.querySelector("canvas.jv-avatar-cena").getBoundingClientRect();
                    return c.width > r.width * 1.3; })()''')
                await ev('document.querySelector(".ringcard").remove()')
                await asyncio.sleep(.3)
                await check('removing the widget releases the live scene', 'jarvisAvatar.montados===0')
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


def test_avatar():
    asyncio.run(main())


if __name__ == '__main__':
    asyncio.run(main())
