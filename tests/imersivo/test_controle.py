"""The JARVIS driving its own screen: commands in, animations on screen, state back.

Run: python tests/test_controle.py   (or pytest)
Reuses the stage harness of test_brain_navigation.py; jarvisd is played by the test,
which writes tela-comando and reads what the page posts to /tela/estado.
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

CANAL = {'comando': {}, 'respostas': []}


class Handler(tb.Handler):
    def do_GET(self):
        if self.path == '/jarvis/tela-comando':
            body = json.dumps(CANAL['comando']).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        assert self.headers['Content-Type'] == 'application/json'
        if self.path == '/tela/estado':
            CANAL['respostas'].append(d)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{}')


def mandar(acoes, idade=0.0):
    pedido = f'p{len(CANAL["respostas"])}-{time.monotonic_ns()}'
    CANAL['comando'] = {'id': pedido, 'acoes': acoes, 'ts': time.time() - idade}
    return pedido


async def resposta(pedido, limite=25):
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        for r in CANAL['respostas']:
            if r.get('resposta') == pedido:
                return r
        await asyncio.sleep(.1)
    raise AssertionError(f'sem resposta para {pedido}')


async def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, passed = [], []
    with tempfile.TemporaryDirectory(prefix='jarvis-controle-') as profile:
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

                await call('Runtime.enable')
                for _ in range(80):
                    if await ev('window.stageReady === true && !!window.jarvisControle && !!window.jarvisCerebro'):
                        break
                    await asyncio.sleep(.1)
                await asyncio.sleep(2)
                assert CANAL['respostas'] and 'estado' in CANAL['respostas'][-1], 'the page does not publish its state'
                e = CANAL['respostas'][-1]['estado']
                assert e['cerebro']['aberto'] is False and e['tema']['opcoes'][0] == 'original'
                assert any(i['nome'] == 'Loja' for i in e['cerebro']['areas']['sessoes']['itens']), e['cerebro']['areas']
                passed.append('the page publishes what is on screen, with areas and items by name and id')

                # A guided tour, like "abre seu cérebro e me mostra as sessões".
                p = mandar([{'acao': 'abrir_cerebro'}, {'acao': 'focar', 'alvo': 'sessoes'},
                            {'acao': 'aguardar', 'valor': 300}, {'acao': 'zoom', 'valor': 1.5}])
                for _ in range(20):
                    if await ev('jarvisBrainGestures.active'):
                        break
                    await asyncio.sleep(.1)
                await check('the brain opens with its animation running', 'jarvisBrainGestures.active && document.getElementById("jv-mapa").classList.contains("on")')
                r = await resposta(p)
                assert all(x['ok'] for x in r['resultados']), r['resultados']
                assert r['resultados'][1]['tipo'] == 'area' and r['estado']['cerebro']['area_expandida'] == 'sessoes'
                assert r['estado']['cerebro']['zoom'] > 0
                passed.append('open, expand Sessões, wait and zoom, each confirmed back')

                p = mandar([{'acao': 'focar', 'alvo': 'LOJA'}])
                r = await resposta(p)
                await check('a name without accents or case finds the item and opens it in Focus',
                            'document.querySelector("#jv-mapa .focus h1")?.textContent==="Loja"')
                assert r['estado']['cerebro']['modo'] == 'foco' and r['estado']['cerebro']['foco']['nome'] == 'Loja'

                p = mandar([{'acao': 'modo', 'valor': 'trabalho'}, {'acao': 'rolar', 'valor': 200},
                            {'acao': 'voltar'}, {'acao': 'enquadrar'}, {'acao': 'mover', 'valor': '40,-20'}])
                r = await resposta(p)
                assert all(x['ok'] for x in r['resultados']), r['resultados']
                passed.append('modes, scrolling, back, fit and pan')

                p = mandar([{'acao': 'focar', 'alvo': 'unicórnio'}, {'acao': 'tema', 'alvo': 'arco-iris'},
                            {'acao': 'brilho', 'valor': 9}, {'acao': 'enquadrar'}])
                r = await resposta(p)
                falhas = [x for x in r['resultados'] if not x['ok']]
                assert [x['acao'] for x in falhas] == ['focar', 'tema', 'brilho'], r['resultados']
                assert 'não achei' in falhas[0]['erro'] and 'marinho' in falhas[1]['erro']
                assert r['resultados'][-1]['ok'], 'one bad step must not stop the rest'
                passed.append('bad steps come back as clear errors and the rest still runs')

                p = mandar([{'acao': 'menu', 'valor': 'abrir'}, {'acao': 'tema', 'alvo': 'marinho'},
                            {'acao': 'brilho', 'valor': 2}])
                r = await resposta(p)
                await check('it can open its own settings and change them', '''!document.getElementById("jv-config").hidden
                    && document.body.classList.contains("tema-marinho") && jarvisMaos.brilho==="MÉDIO"''')
                assert r['estado']['menu_configuracoes']['aberto'] and r['estado']['tema']['atual'] == 'marinho'
                assert r['estado']['brilho_camera'] == 'MÉDIO'

                p = mandar([{'acao': 'menu', 'valor': 'fechar'}, {'acao': 'tema', 'alvo': 'original'},
                            {'acao': 'brilho', 'valor': 0}, {'acao': 'fechar_cerebro'}])
                r = await resposta(p)
                await asyncio.sleep(.4)
                await check('and put everything back', '''document.getElementById("jv-config").hidden && !document.body.classList.contains("tema-ativo")
                    && !jarvisBrainGestures.active''')

                # The Núcleo is the ring and its orbs: open it, open the Guia, a note by stem.
                p = mandar([{'acao': 'nucleo', 'valor': 'abrir'}, {'acao': 'abrir', 'alvo': 'guia'}])
                r = await resposta(p)
                assert all(x['ok'] for x in r['resultados']), r['resultados']
                await asyncio.sleep(.8)
                await check('"abre o guia do núcleo" opens the orbs and exactly the Guia pane',
                            '''document.querySelectorAll(".card.orb").length===5
                    && [...document.querySelectorAll(".panel.browser h3")].map(h=>h.textContent).join()==="GUIA"''')
                p = mandar([{'acao': 'abrir', 'alvo': 'primeiro'}])
                r = await resposta(p)
                assert r['resultados'][0]['ok'] and r['resultados'][0]['abriu'] == 'Primeiros passos', r['resultados']
                n = r['estado']['nucleo']
                assert n['aberto'] and n['orbes_abertos'] == ['Guia'] and n['notas_abertas'] == ['Primeiros passos'], n
                passed.append('a note opens by a spoken stem, and the state lists orbs, panes and notes')
                p = mandar([{'acao': 'abrir', 'alvo': 'acervo'}, {'acao': 'fechar', 'alvo': 'Guia'},
                            {'acao': 'abrir', 'alvo': 'planilha'}])
                r = await resposta(p)
                assert [x['ok'] for x in r['resultados']] == [True, True, False], r['resultados']
                assert 'Acervo' in r['resultados'][2]['erro'], r['resultados'][2]
                assert r['estado']['nucleo']['orbes_abertos'] == ['Acervo'], r['estado']['nucleo']
                # One catalogue over every orb: files by their clean spoken name, an orb to narrow it.
                p = mandar([{'acao': 'abrir', 'alvo': 'burrinho'}, {'acao': 'buscar', 'alvo': 'porto', 'orbe': 'Acervo'},
                            {'acao': 'abrir', 'alvo': 'Acervo/porto pe'}, {'acao': 'abrir', 'alvo': 'burrinho', 'orbe': 'Guia'},
                            {'acao': 'abrir', 'alvo': 'x', 'orbe': 'Pokédex'}])
                r = await resposta(p)
                res = r['resultados']
                assert res[0]['ok'] and res[0]['abriu'] == 'burrinho' and res[0]['orbe'] == 'Acervo', res[0]
                assert res[0]['endereco'] == 'acervo/misc/burrinho_refeito_final.png', res[0]
                assert res[1]['achados'][0] == {'nome': 'porto pe', 'orbe': 'Acervo', 'tipo': 'arquivo',
                                                'endereco': 'acervo/misc/porto_pe_final.png'}, res[1]
                assert res[2]['ok'] and res[2]['abriu'] == 'porto pe', res[2]
                assert not res[3]['ok'] and 'no Guia' in res[3]['erro'], res[3]
                assert not res[4]['ok'] and 'Pokédex' in res[4]['erro'] and 'Trabalho' in res[4]['erro'], res[4]
                assert sorted(r['estado']['nucleo']['arquivos_abertos']) == ['burrinho', 'porto pe'], r['estado']['nucleo']
                await check('"abre o burrinho" finds the Acervo file and shows it on the board',
                            '[...document.querySelectorAll(".imgcard img")].some(i => i.src.endsWith("/media/misc/burrinho_refeito_final.png"))')
                p = mandar([{'acao': 'fechar', 'alvo': 'burrinho'}])
                r = await resposta(p)
                assert r['resultados'][0]['ok'] and r['estado']['nucleo']['arquivos_abertos'] == ['porto pe'], r
                passed.append('an orb narrows the search, buscar lists addresses, and an open file closes by name')

                # Hoje and Trabalho are doors into the Mapa: the Foco board and the Work view.
                p = mandar([{'acao': 'abrir', 'alvo': 'Trabalho'}])
                r = await resposta(p)
                assert r['resultados'][0]['ok'], r['resultados']
                await check('the Trabalho orb opens the Mapa on the sessions', 'document.querySelector("#jv-mapa").dataset.mode==="work" && document.querySelector(".work").textContent.includes("Loja")')
                p = mandar([{'acao': 'abrir', 'alvo': 'meu dia'}])
                r = await resposta(p)
                assert r['resultados'][0]['ok'], r['resultados']
                await check('the Hoje orb (by its alias) opens the Foco board', 'document.querySelector("#jv-mapa").dataset.mode==="focus" && document.querySelector(".focus").textContent.includes("Lançar o Ligatia")')
                p = mandar([{'acao': 'modo', 'valor': 'geral'}, {'acao': 'abrir', 'alvo': 'seu cérebro'}])
                r = await resposta(p)
                assert [x['ok'] for x in r['resultados']] == [True, True], r['resultados']
                assert r['resultados'][1] == {'acao': 'abrir', 'ok': True, 'abriu': 'Mapa', 'tipo': 'orbe'}
                assert r['estado']['cerebro']['aberto'] and 'Mapa' in r['estado']['nucleo']['orbes_abertos']
                passed.append('Hoje and Trabalho open their views, "geral" is the overview, and "seu cérebro" is the Mapa')

                p = mandar([{'acao': 'fechar', 'alvo': 'tudo'}])
                r = await resposta(p)
                await asyncio.sleep(.8)
                await check('and "fecha tudo" closes panes, notes and the orbs',
                            '!document.querySelector(".card.orb") && !document.querySelector(".panel")')
                assert not r['estado']['nucleo']['aberto']

                # The hands come first: during a pinch the JARVIS waits for the hand to rest.
                await ev('''jarvisMaos.amostra(0,{ratio:.2,ratio3:.1,f8v:1,backMean:1.5,aspect:2.5,tRel:.5,pinched:true,
                    x:1,y:1,hspd:0,now:performance.now(),caixa:[.3,.3,.6,.6]})''')
                p2 = mandar([{'acao': 'tema', 'alvo': 'roxo'}])
                await asyncio.sleep(.6)
                await check('during a pinch, nothing moves under the hand', '!document.body.classList.contains("tema-roxo") && jarvisMaos.emUso')
                assert any(x.get('recebido') == p2 and x['estado']['maos_em_uso'] for x in CANAL['respostas']), 'no start ack / hands flag'
                r = await resposta(p2)
                await check('and it runs once the hand rests', 'document.body.classList.contains("tema-roxo")')
                await ev('jarvisTema.usar("original")')

                # Runs once: undo its effect by hand; a second run would redo it.
                p3 = mandar([{'acao': 'brilho', 'valor': 1}])
                await resposta(p3)
                await ev('jarvisMaos.mudarBrilho(0)')
                await asyncio.sleep(1.2)
                assert await ev('jarvisMaos.brilho==="DESLIGADO"'), 'a command ran twice'
                passed.append('a command runs once')
                velho = mandar([{'acao': 'abrir_cerebro'}], idade=60)
                await asyncio.sleep(1.2)
                assert not any(x.get('resposta') == velho for x in CANAL['respostas']), 'an old command was replayed'
                await check('an old command (reload, stopped page) is never replayed', '!jarvisBrainGestures.active')
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


def test_jarvis_drives_its_own_screen():
    asyncio.run(main())


if __name__ == '__main__':
    asyncio.run(main())
