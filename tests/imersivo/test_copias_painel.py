"""Botões reais do painel, API e Git em uma instalação temporária, sem agentes de modelo."""

import asyncio
import json
import subprocess
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import websockets

from jarvis.oficina.sessoes import Sessoes, _git
from jarvis.portal.acoes import Acoes
from jarvis.portal.servidor import Portal


async def verificar(tmp_path):
    projeto = tmp_path / 'projeto'
    projeto.mkdir()
    (projeto / 'a.txt').write_text('base\n')
    for args in [('init', '-q'), ('config', 'user.name', 'Teste'),
                 ('config', 'user.email', 'teste@example.invalid'), ('add', '.'),
                 ('commit', '-qm', 'base')]:
        assert _git(projeto, *args).returncode == 0
    sessoes = Sessoes(tmp_path / 'sessoes', (tmp_path,), rodar=lambda *a: None)
    sessao = sessoes.criar('Teste', str(projeto), isolada=True)
    onde = Path(sessao.worktree)
    (onde / 'a.txt').write_text('aplicado\n')
    assert _git(onde, 'add', '.').returncode == 0
    assert _git(onde, 'commit', '-qm', 'mudança').returncode == 0
    acoes = Acoes(SimpleNamespace(sessoes=sessoes), tmp_path/'latencias', tmp_path/'teste')
    escritas = {
        'sessao/ler': acoes.ler_sessao,
        'sessao/copia': lambda d: sessoes.copia(d['id']),
        'sessao/copia/aplicar': acoes.aplicar_copia,
        'sessao/copia/descartar': acoes.descartar_copia,
        'sessao/arquivos': acoes.arquivos,
        'terminal/abrir': lambda d: {'posicao': 0},
        'terminal/ler': lambda d: {'posicao': 0, 'vivo': False, 'dados': ''},
        'painel/vendo': lambda d: {},
    }
    p = Portal({
        'sessoes': lambda: [acoes._sessao(sessoes.ler(sessao.id))],
        'contas': lambda: {'agentes': []},
        'configuracao': lambda: {'feita': True},
        'estado': lambda: {'ze': 'ativo', 'modo_fala': 'silencioso', 'inicio': 1},
    }, escritas, porta=0)
    p.iniciar()
    perfil = tmp_path / 'chromium'
    processo = subprocess.Popen([
        '/usr/bin/chromium', '--headless=new', '--remote-debugging-port=0',
        f'--user-data-dir={perfil}', '--no-first-run', '--disable-background-networking',
        f'{p.endereco}#sessoes',
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        porta = perfil / 'DevToolsActivePort'
        for _ in range(100):
            if porta.exists(): break
            await asyncio.sleep(.1)
        with urllib.request.urlopen(
            f'http://127.0.0.1:{porta.read_text().splitlines()[0]}/json/list', timeout=5
        ) as r:
            alvo = next(x for x in json.load(r) if x['type'] == 'page')
        async with websockets.connect(alvo['webSocketDebuggerUrl']) as ws:
            numero = 0
            async def avaliar(texto):
                nonlocal numero
                numero += 1
                await ws.send(json.dumps({'id': numero, 'method': 'Runtime.evaluate', 'params': {
                    'expression': texto, 'awaitPromise': True, 'returnByValue': True,
                }}))
                while True:
                    resposta = json.loads(await asyncio.wait_for(ws.recv(), 10))
                    if resposta.get('id') == numero:
                        assert 'exceptionDetails' not in resposta['result'], resposta
                        return resposta['result'].get('result', {}).get('value')
            async def esperar(texto):
                for _ in range(80):
                    if await avaliar(texto): return
                    await asyncio.sleep(.1)
                tela = await avaliar('document.body.innerText.slice(-1200)')
                raise AssertionError(f'{texto}: {tela}')
            await esperar("!!document.querySelector('[data-acao=sessao-abrir]')")
            await avaliar("document.querySelector('[data-acao=sessao-abrir]').click()")
            await esperar("!!document.querySelector('[data-acao=copia-aplicar]:not(:disabled)')")
            assert await avaliar("document.getElementById('copia-sessao').getBoundingClientRect().height > 0")
            await avaliar("document.querySelector('[data-acao=copia-aplicar]').click()")
            assert (projeto / 'a.txt').read_text() == 'base\n'
            await esperar("!!document.querySelector('[data-acao=confirmar-sim]')")
            await avaliar("document.querySelector('[data-acao=confirmar-sim]').click()")
            await esperar("!!document.querySelector('[data-acao=copia-aplicar]:disabled')")
            assert (projeto / 'a.txt').read_text() == 'aplicado\n'
            (onde / 'a.txt').write_text('descartar\n')
            await avaliar("document.querySelector('[data-acao=copia-atualizar]').click()")
            await esperar("!!document.querySelector('[data-acao=copia-descartar]:not(:disabled)')")
            await avaliar("document.querySelector('[data-acao=copia-descartar]').click()")
            assert (onde / 'a.txt').read_text() == 'descartar\n'
            await avaliar("document.querySelector('[data-acao=confirmar-sim]').click()")
            await esperar("!!document.querySelector('[data-acao=copia-descartar]:disabled')")
            assert (onde / 'a.txt').read_text() == 'aplicado\n'
            assert (projeto / 'a.txt').read_text() == 'aplicado\n'
            # A configuração inicial não tem entrada no menu lateral.
            await avaliar('carregarPagina("configurar")')  # sob demanda; depois troca o conteúdo
            await avaliar('PAGINAS.configurar = async () => "<h1>Configuração</h1>"')
            await avaliar('(async () => { location.hash = "#configurar"; await abrir(); })()')
            assert await avaliar('document.querySelector("#conteudo h1").textContent') == 'Configuração'
    finally:
        processo.terminate()
        try: processo.wait(timeout=5)
        except subprocess.TimeoutExpired:
            processo.kill(); processo.wait(timeout=5)
        p.parar()


def test_aplicar_e_descartar_exigem_confirmacao_no_painel(tmp_path):
    asyncio.run(verificar(tmp_path))
