"""O painel num Chromium de verdade: todas as páginas abrem, sem erro no console.

O `tsc` não enxerga a ordem em que os scripts carregam; uma função de página sob demanda usada
cedo demais derruba o painel inteiro e só aparece no navegador. As leituras vêm de
`painel_respostas.json`, no formato real e sem dados de ninguém; as escritas que as páginas fazem
ao abrir também. Sem Chromium, o teste é pulado; na CI (`ZE_SEM_PULOS=1`), pulado é falha.
"""

import asyncio
import base64
import contextlib
import copy
import json
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import websockets

from jarvis.oficina.progresso import Progresso
from jarvis.portal.acoes import Acoes
from jarvis.portal.servidor import WEB, Escrita, Leitura, PedidoInvalido, Portal

RESPOSTAS = Path(__file__).with_name("painel_respostas.json")
CHROMIUM = next(
    (
        c
        for c in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
        if shutil.which(c)
    ),
    None,
)


def _paginas() -> list[str]:
    """As páginas do menu e as carregadas sob demanda, lidas do próprio painel."""
    html = (WEB / "index.html").read_text()
    menu = re.findall(r'data-secao="([a-z]+)"', html)
    navegacao = (WEB / "modulos/navegacao.js").read_text()
    sob_demanda = re.findall(r'"([a-z]+)":"/paginas/', navegacao)
    return sorted({*menu, *sob_demanda} - {"imersao"})  # imersão é outro servidor


def test_respostas_cobrem_todas_as_leituras(tmp_path: Path) -> None:
    leituras = Acoes(SimpleNamespace(), tmp_path, tmp_path).leituras()
    respostas = json.loads(RESPOSTAS.read_text())
    assert sorted(respostas["leituras"]) == sorted(leituras)
    assert set(respostas["escritas"]) <= set(
        Acoes(SimpleNamespace(), tmp_path, tmp_path).escritas()
    )


class _Navegador:
    def __init__(self, ws: Any) -> None:
        self.ws = ws
        self.numero = 0
        self.erros: list[str] = []

    async def avaliar(self, expressao: str) -> Any:
        self.numero += 1
        numero = self.numero
        await self.ws.send(
            json.dumps(
                {
                    "id": numero,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expressao,
                        "awaitPromise": True,
                        "returnByValue": True,
                    },
                }
            )
        )
        while True:
            resposta = json.loads(await asyncio.wait_for(self.ws.recv(), 15))
            metodo = resposta.get("method")
            if metodo == "Runtime.exceptionThrown":
                detalhe = resposta["params"]["exceptionDetails"]
                self.erros.append(
                    detalhe.get("exception", {}).get("description") or detalhe["text"]
                )
            elif metodo == "Runtime.consoleAPICalled" and resposta["params"]["type"] == "error":
                self.erros.append(json.dumps(resposta["params"]["args"], ensure_ascii=False))
            if resposta.get("id") == numero:
                resultado = resposta["result"]
                if "exceptionDetails" in resultado:
                    self.erros.append(resultado["exceptionDetails"]["text"])
                return resultado.get("result", {}).get("value")


def _chromium(perfil: Path) -> tuple[subprocess.Popen[bytes], str]:
    """Um Chromium sem tela e o endereço de depuração da aba dele."""
    perfil.mkdir(parents=True, exist_ok=True)
    registro = perfil.with_name("chromium.log")
    with registro.open("wb") as saida:
        processo = subprocess.Popen(  # noqa: S603 (o Chromium da máquina, argumentos fixos)
            [
                str(CHROMIUM),
                "--headless=new",
                "--remote-debugging-port=0",
                f"--user-data-dir={perfil}",
                "--no-first-run",
                "--disable-background-networking",
                "--window-size=1400,900",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=saida,
        )
    porta = perfil / "DevToolsActivePort"
    # 30 s: na CI, a primeira abertura do Chromium passou de 15 s (16/10/2026).
    for _ in range(300):
        if porta.exists() and porta.read_text().strip():
            break
        if processo.poll() is not None:
            break
        time.sleep(0.1)
    else:
        processo.kill()
        raise RuntimeError(f"O Chromium ({CHROMIUM}) não abriu em 30 s.")
    if not (porta.exists() and porta.read_text().strip()):
        # Sem isso, a falha era só "DevToolsActivePort não existe" (lição de 16/10/2026). O erro
        # do dbus aparece sempre numa máquina sem sessão e não derruba nada: o motivo é o FATAL.
        linhas = registro.read_text(errors="replace").splitlines()
        motivo = [x for x in linhas if "FATAL" in x] or linhas[-5:]
        raise RuntimeError(f"O Chromium ({CHROMIUM}) saiu ao abrir: {' | '.join(motivo[:5])}")
    lista = f"http://127.0.0.1:{porta.read_text().splitlines()[0]}/json/list"
    with urllib.request.urlopen(lista, timeout=15) as r:
        alvo = next(x for x in json.load(r) if x["type"] == "page")
    return processo, alvo["webSocketDebuggerUrl"]


async def _carregar(nav: _Navegador, endereco: str) -> None:
    await nav.avaliar("0")
    await nav.ws.send(json.dumps({"id": 0, "method": "Runtime.enable"}))
    await nav.avaliar(f"location.href = {json.dumps(endereco)}")
    for _ in range(100):
        if await nav.avaliar(
            "typeof abrir === 'function' && !!document.querySelector('#conteudo')"
        ):
            break
        await asyncio.sleep(0.1)
    await asyncio.sleep(0.5)


async def _percorrer(depuracao: str, endereco: str) -> dict[str, tuple[list[str], str]]:
    resultado: dict[str, tuple[list[str], str]] = {}
    async with websockets.connect(depuracao, max_size=None) as ws:
        nav = _Navegador(ws)
        await _carregar(nav, endereco)
        resultado["abertura"] = (nav.erros[:], "")
        for pagina in _paginas():
            nav.erros.clear()
            await nav.avaliar(f'(async () => {{ location.hash = "#{pagina}"; await abrir(); }})()')
            await asyncio.sleep(0.3)  # o que a página prepara depois de desenhar
            texto = await nav.avaliar('document.querySelector("#conteudo").innerText') or ""
            resultado[pagina] = (nav.erros[:], texto)
    return resultado


async def _clicar_rapido(depuracao: str, endereco: str, ordem: list[str]) -> tuple[list[str], str]:
    """Cliques no menu mais rápidos que as respostas do Zé; a última página é a que fica."""
    async with websockets.connect(depuracao, max_size=None) as ws:
        nav = _Navegador(ws)
        await _carregar(nav, endereco)
        nav.erros.clear()
        for pagina in ordem:
            await nav.avaliar(f"document.querySelector('nav a[data-secao=\"{pagina}\"]').click()")
            await asyncio.sleep(0.05)
        await asyncio.sleep(2)  # todas as respostas atrasadas já voltaram
        texto = await nav.avaliar('document.querySelector("#conteudo").innerText') or ""
        return nav.erros[:], texto


def _escrita(resposta: Any) -> Escrita:
    return lambda _dados: copy.deepcopy(resposta)


@contextlib.contextmanager
def _painel(
    tmp_path: Path,
    atraso_s: float = 0.0,
    extras: dict[str, Escrita] | None = None,
    estado: Leitura | None = None,
    trocas: dict[str, Any] | None = None,
    entrada_terminal: Escrita | None = None,
    leituras_vivas: dict[str, Leitura] | None = None,
) -> Iterator[tuple[str, str]]:
    """O painel com as respostas de exemplo e um Chromium apontado para ele."""
    respostas = json.loads(RESPOSTAS.read_text())

    def leitura(valor: Any) -> Leitura:
        def ler() -> Any:
            time.sleep(atraso_s)
            return copy.deepcopy(valor)

        return ler

    leituras = {nome: leitura(v) for nome, v in respostas["leituras"].items()}
    for nome, valor in (trocas or {}).items():
        leituras[nome] = leitura(valor)
    if estado is not None:
        leituras["estado"] = estado
    leituras.update(leituras_vivas or {})
    nomes = Acoes(SimpleNamespace(), tmp_path, tmp_path).escritas()
    escritas = {nome: _escrita(respostas["escritas"].get(nome, {})) for nome in nomes}
    escritas.update(extras or {})
    portal = Portal(leituras, escritas, porta=0, entrada_terminal=entrada_terminal)
    portal.iniciar()
    processo, depuracao = _chromium(tmp_path / "chromium")
    try:
        yield depuracao, portal.endereco
    finally:
        processo.terminate()
        try:
            processo.wait(timeout=5)
        except subprocess.TimeoutExpired:
            processo.kill()
        portal.parar()


def _quebrada(texto: str) -> bool:
    return "Não foi possível abrir a página" in texto or not texto.strip()


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
def test_todas_as_paginas_abrem_sem_erro(tmp_path: Path) -> None:
    with _painel(tmp_path) as (depuracao, endereco):
        resultado = asyncio.run(_percorrer(depuracao, endereco))
    assert set(resultado) == {"abertura", *_paginas()}
    falhas = {
        pagina: erros or texto[:200]
        for pagina, (erros, texto) in resultado.items()
        if erros or (pagina != "abertura" and _quebrada(texto))
    }
    assert not falhas, falhas


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
def test_clicar_rapido_no_menu_mostra_a_ultima_pagina(tmp_path: Path) -> None:
    # Caso real de 15/10/2026: a página anterior voltava depois e quebrava a nova
    # ("Cannot set properties of null").
    ordem = ["sessoes", "conversa", "memoria", "melhorias", "skills", "conversa", "sessoes"]
    with _painel(tmp_path, atraso_s=0.2) as (depuracao, endereco):
        erros, texto = asyncio.run(_clicar_rapido(depuracao, endereco, ordem))
    assert not erros, erros
    assert not _quebrada(texto), texto[:200]
    assert texto.startswith("SESSÕES"), texto[:200]


async def _alternar_com_terminal(depuracao: str, endereco: str) -> float:
    """Abre uma sessão e alterna rápido com o Início; devolve quanto um pedido comum demora."""
    async with websockets.connect(depuracao, max_size=None) as ws:
        nav = _Navegador(ws)
        await _carregar(nav, endereco + "#sessoes")
        await nav.avaliar("document.querySelector('.item-sessao').click()")
        await asyncio.sleep(0.5)
        for _ in range(6):
            await nav.avaliar("document.querySelector('nav a[data-secao=\"inicio\"]').click()")
            await asyncio.sleep(0.1)
            await nav.avaliar("document.querySelector('nav a[data-secao=\"sessoes\"]').click()")
            await asyncio.sleep(0.3)
        espera = await nav.avaliar(
            "(async () => { const t = performance.now(); await api('estado');"
            " return performance.now() - t; })()"
        )
        assert not nav.erros, nav.erros
        return float(espera)


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
def test_trocar_de_aba_solta_a_leitura_do_terminal(tmp_path: Path) -> None:
    # Caso real de 15/10/2026: cada visita deixava uma leitura do terminal presa (até 20 s no
    # servidor). Seis presas esgotam as conexões do navegador e o painel inteiro fica lento; e o
    # laço antigo, vivo de novo ao voltar à mesma sessão, escrevia em dobro no terminal.
    inicios: list[float] = []

    def ler_terminal(_dados: dict[str, Any]) -> dict[str, Any]:
        inicios.append(time.monotonic())
        time.sleep(3)  # a espera longa do terminal de verdade, encurtada
        return {"posicao": 0, "vivo": True, "dados": ""}

    with _painel(tmp_path, extras={"terminal/ler": ler_terminal}) as (depuracao, endereco):
        espera_ms = asyncio.run(_alternar_com_terminal(depuracao, endereco))
        fim = time.monotonic()
        time.sleep(3.5)
        depois = [t for t in inicios if t > fim]
    assert espera_ms < 1000, espera_ms
    assert len(depois) <= 1, f"{len(depois)} leituras do terminal ao mesmo tempo"


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
def test_terminal_acompanha_fallback_sem_reabrir_a_pagina(tmp_path: Path) -> None:
    leituras: list[dict[str, Any]] = []

    def ler(dados: dict[str, Any]) -> dict[str, Any]:
        leituras.append(dados)
        numero = len(leituras)
        if numero == 1:
            return {
                "posicao": 5000,
                "vivo": True,
                "geracao": 11,
                "dados": base64.b64encode(b"Conta anterior\r\n").decode(),
            }
        if numero == 2:
            return {"posicao": 5000, "vivo": False, "geracao": 11, "dados": "", "trocando": True}
        if numero == 3:
            return {
                "posicao": 24,
                "vivo": True,
                "geracao": 22,
                "reiniciado": True,
                "dados": base64.b64encode(b"Nova conta trabalhando\r\n").decode(),
            }
        time.sleep(0.2)
        return {"posicao": 24, "vivo": True, "geracao": 22, "dados": ""}

    async def conferir(depuracao: str, endereco: str) -> None:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#melhorias")
            await _esperar(
                nav,
                "typeof term !== 'undefined' && !!term && "
                "term.buffer.active.getLine(0)?.translateToString(true) "
                "=== 'Nova conta trabalhando'",
            )
            assert await nav.avaliar("document.getElementById('terminal-fechado').hidden")
            assert not nav.erros

    with _painel(tmp_path, extras={"terminal/ler": ler}) as (depuracao, endereco):
        asyncio.run(conferir(depuracao, endereco))
    assert leituras[2]["geracao"] == 11
    assert leituras[3]["geracao"] == 22 and leituras[3]["desde"] == 24


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
def test_terminal_envia_teclas_pelo_websocket_e_fecha_ao_trocar_de_pagina(
    tmp_path: Path,
) -> None:
    recebidas: list[str] = []
    chegaram = threading.Event()

    def entrada(dados: dict[str, Any]) -> None:
        recebidas.append(str(dados["dados"]))
        if len(recebidas) == 2:
            chegaram.set()

    async def conferir(depuracao: str, endereco: str) -> None:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#sessoes")
            await nav.avaliar("document.querySelector('.item-sessao').click()")
            await _esperar(nav, "!!term && !!termWs && termWsPronto")
            await nav.avaliar("escreverNoTerminal('co'); escreverNoTerminal('dex\\r')")
            assert await asyncio.to_thread(chegaram.wait, 3)
            await nav.avaliar("document.querySelector('nav a[data-secao=\"inicio\"]').click()")
            await _esperar(nav, "!termWs")
            assert not nav.erros, nav.erros

    with _painel(tmp_path, entrada_terminal=entrada) as (depuracao, endereco):
        asyncio.run(conferir(depuracao, endereco))
    assert recebidas == ["co", "dex\r"]


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
def test_terminal_recorre_ao_http_se_o_websocket_nao_estiver_disponivel(
    tmp_path: Path,
) -> None:
    escritas: list[str] = []
    chegou = threading.Event()

    def escrever(dados: dict[str, Any]) -> None:
        escritas.append(str(dados["dados"]))
        chegou.set()

    async def conferir(depuracao: str, endereco: str) -> None:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#sessoes")
            await nav.avaliar("document.querySelector('.item-sessao').click()")
            await _esperar(nav, "!!term && !!termId")
            await nav.avaliar("escreverNoTerminal('fallback')")
            assert await asyncio.to_thread(chegou.wait, 5)
            assert not nav.erros, nav.erros

    with _painel(tmp_path, extras={"terminal/escrever": escrever}) as (
        depuracao,
        endereco,
    ):
        asyncio.run(conferir(depuracao, endereco))
    assert escritas == ["fallback"]


async def _layout_do_autodesenvolvimento(depuracao: str, endereco: str) -> dict[str, Any]:
    async with websockets.connect(depuracao, max_size=None) as ws:
        nav = _Navegador(ws)
        await _carregar(nav, endereco + "#melhorias")
        await asyncio.sleep(1)
        medir = (
            "(() => { const f = (q) => document.querySelector(q)?.getBoundingClientRect();"
            " const c = document.querySelector('.sessao-aberta > .conversa');"
            " return { pagina: f('#conteudo').bottom, sessao: f('.sessao-aberta').bottom,"
            " terminal: c ? getComputedStyle(c).display : 'ausente' }; })()"
        )
        larga = await nav.avaliar(medir)
        await ws.send(
            json.dumps(
                {
                    "id": 0,
                    "method": "Emulation.setDeviceMetricsOverride",
                    "params": {
                        "width": 900,
                        "height": 700,
                        "deviceScaleFactor": 1,
                        "mobile": False,
                    },
                }
            )
        )
        await asyncio.sleep(0.5)
        estreita = await nav.avaliar(medir)
        assert not nav.erros, nav.erros
        return {"larga": larga, "estreita": estreita}


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
def test_terminal_do_autodesenvolvimento_ocupa_a_tela_e_nao_some(tmp_path: Path) -> None:
    # Casos reais de 15/10/2026: com o diagnóstico oculto, a sessão ficava com a altura do
    # conteúdo e sobrava tela vazia embaixo; e ao estreitar a janela com os arquivos abertos, o
    # terminal sumia.
    with _painel(tmp_path) as (depuracao, endereco):
        medidas = asyncio.run(_layout_do_autodesenvolvimento(depuracao, endereco))
    larga, estreita = medidas["larga"], medidas["estreita"]
    assert abs(larga["pagina"] - larga["sessao"]) < 2, larga
    assert larga["terminal"] != "none", larga
    assert estreita["terminal"] != "none", estreita


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
def test_central_concluida_libera_espaco_e_terminal_permite_rolar(tmp_path: Path) -> None:
    respostas = json.loads(RESPOSTAS.read_text())
    central = respostas["escritas"]["ze/central"]
    central.update(estado="concluida", aviso="Sessões unificadas. Histórico preservado.")

    async def conferir(depuracao: str, endereco: str) -> None:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#melhorias")
            await _esperar(nav, "!!termId && !!document.querySelector('#terminal .xterm')")
            assert await nav.avaliar("document.querySelector('#centralizacao').hidden")
            await nav.avaliar(
                "new Promise(ok => term.write(Array.from({length: 200}, (_, i) =>"
                " `Linha ${i}\\r\\n`).join(''), ok))"
            )
            await _esperar(nav, "term.buffer.active.baseY > 100")
            await asyncio.sleep(0.2)
            medidas = await nav.avaliar(
                "(() => { const v = document.querySelector("
                "'.xterm-scrollable-element > .scrollbar.vertical');"
                " const r = v.getBoundingClientRect(); return {x: r.right - 5,"
                " y: r.top + r.height / 2, bottom: r.bottom,"
                " fim: document.querySelector('#conteudo').getBoundingClientRect().bottom,"
                " barra: r.width}; })()"
            )
            assert medidas["bottom"] <= medidas["fim"] + 1, medidas
            assert medidas["barra"] >= 10, medidas
            # Um evento real do Chromium, em vez de chamar scrollToLine e provar só a API.
            await ws.send(
                json.dumps(
                    {
                        "id": 0,
                        "method": "Input.dispatchMouseEvent",
                        "params": {
                            "type": "mouseWheel",
                            "x": medidas["x"] - 40,
                            "y": medidas["y"],
                            "deltaX": 0,
                            "deltaY": -400,
                        },
                    }
                )
            )
            await _esperar(nav, "term.buffer.active.viewportY < term.buffer.active.baseY")
            posicao = await nav.avaliar("term.buffer.active.viewportY")
            await nav.avaliar("new Promise(ok => term.write('Outra saída\\r\\n', ok))")
            assert await nav.avaliar("term.buffer.active.viewportY") == posicao
            # Clicar no trilho também deve alcançar a barra, sem uma camada cobrindo-a.
            for tipo in ("mousePressed", "mouseReleased"):
                await ws.send(
                    json.dumps(
                        {
                            "id": 0,
                            "method": "Input.dispatchMouseEvent",
                            "params": {
                                "type": tipo,
                                "x": medidas["x"],
                                "y": medidas["y"],
                                "button": "left",
                                "clickCount": 1,
                            },
                        }
                    )
                )
            await _esperar(nav, f"term.buffer.active.viewportY < {posicao}")
            assert await nav.avaliar(
                "getComputedStyle(document.querySelector('.xterm-viewport')).overflowY === 'hidden'"
            )
            await nav.avaliar("acompanharCentral()")
            assert await nav.avaliar("document.querySelector('#centralizacao').hidden")
            assert not nav.erros, nav.erros

    with _painel(tmp_path, extras={"ze/central": lambda _: central}) as (depuracao, endereco):
        asyncio.run(conferir(depuracao, endereco))


class _AtualizacaoDeTeste:
    """A API usa o progresso real; o teste escolhe quando termina cada etapa, sem atualizar o PC."""

    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta
        self.progresso = Progresso(pasta)
        self.pid = 1

    def estado(self) -> dict[str, Any]:
        base = json.loads(RESPOSTAS.read_text())["leituras"]["estado"]
        return {**base, "inicio": self.pid, "atualizacao": self.progresso.foto()}

    def aplicar(self, dados: dict[str, Any]) -> dict[str, str]:
        self.progresso.comecar()
        self.progresso.etapa("testes_copia")
        return {"aviso": "Aplicando melhorias."}

    def etapa(self, dados: dict[str, Any]) -> dict[str, str]:
        nome = str(dados["nome"])
        if nome == "aguardando":
            self.progresso.aguardar()
        elif nome == "cancelada":
            self.progresso.cancelar_espera()
        elif nome == "falhou":
            self.progresso.falhou("Os testes falharam. <texto>")
        elif nome in ("pronto", "voltou"):
            self.progresso = Progresso(self.pasta)
            self.progresso.etapa(nome)
            self.pid += 1  # o batimento deve recarregar a página, sem perder o resultado
        else:
            self.progresso.etapa(nome)
        return {}


async def _esperar(nav: _Navegador, condicao: str) -> None:
    for _ in range(70):
        if await nav.avaliar(condicao):
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"O painel não chegou ao estado esperado: {condicao}")


async def _ver_atualizacao(depuracao: str, endereco: str, resultado: str) -> None:
    async with websockets.connect(depuracao, max_size=None) as ws:
        nav = _Navegador(ws)
        await _carregar(nav, endereco + "#melhorias")
        await _esperar(
            nav, "!!document.querySelector('[data-acao=melhorias-aplicar]:not(:disabled)')"
        )
        await nav.avaliar("document.querySelector('[data-acao=melhorias-aplicar]').click()")
        await _esperar(
            nav, "document.querySelector('.atualizacao')?.dataset.estado === 'aplicando'"
        )
        medir_barra = (
            "(() => { const c = document.querySelector('.atualizacao').getBoundingClientRect();"
            " const b = document.querySelector('.atualizacao .barra').getBoundingClientRect();"
            " return {cartao:c.width, barra:b.width, esquerda:c.left, direita:c.right,"
            " topo:c.top, fundo:c.bottom, largura:innerWidth, altura:innerHeight}; })()"
        )
        medidas = await nav.avaliar(medir_barra)
        assert medidas["barra"] > medidas["cartao"] * 0.8, medidas
        if resultado == "pronto":
            await ws.send(
                json.dumps(
                    {
                        "id": 0,
                        "method": "Emulation.setDeviceMetricsOverride",
                        "params": {
                            "width": 390,
                            "height": 844,
                            "deviceScaleFactor": 1,
                            "mobile": False,
                        },
                    }
                )
            )
            await asyncio.sleep(0.1)
            medidas = await nav.avaliar(medir_barra)
            assert 0 <= medidas["esquerda"] < medidas["direita"] <= medidas["largura"], medidas
            assert 0 <= medidas["topo"] < medidas["fundo"] <= medidas["altura"], medidas
            assert medidas["barra"] > medidas["cartao"] * 0.8, medidas
        assert await nav.avaliar(
            "document.querySelector('.atualizacao').innerText.includes('Verificando melhorias')"
        )
        assert await nav.avaliar("document.querySelector('[data-acao=melhorias-aplicar]').disabled")
        await nav.avaliar("location.hash = '#memoria'")
        await _esperar(nav, "document.querySelector('#conteudo h1')?.textContent === 'Memória'")
        assert await nav.avaliar("!!document.querySelector('.atualizacao')")
        # Uma queda durante os testes continua sendo sinalizada, mesmo com a barra presente.
        sem_conexao = (
            "(async () => { const f = window.fetch;"
            " window.fetch = () => Promise.reject(new TypeError('sem conexão'));"
            " try { for (let i=0; i<3; i++) await batimento(); }"
            " finally { window.fetch = f; }"
            " return !!document.querySelector('.faixa-fora'); })()"
        )
        assert await nav.avaliar(sem_conexao)
        await nav.avaliar("batimento()")
        if resultado == "falhou":
            await nav.avaliar("api('teste/etapa', {nome: 'falhou'})")
        else:
            for etapa in ("juntando", "testes_ze", "reiniciando"):
                await nav.avaliar(f"api('teste/etapa', {{nome: '{etapa}'}})")
                await nav.avaliar("batimento()")
            assert not await nav.avaliar(sem_conexao)  # desconexão esperada no reinício
            await nav.avaliar("atualizacaoRecebida -= 300001")
            assert await nav.avaliar(sem_conexao)  # não esconde indefinidamente uma queda real
            await nav.avaliar("batimento()")
            # Reiniciar é esperado: a página mantém a indicação e o percentual abaixo de 100.
            assert await nav.avaliar(
                "Number(document.querySelector('.atualizacao [role=progressbar]')"
                ".getAttribute('aria-valuenow')) < 100"
            )
            await nav.avaliar(f"api('teste/etapa', {{nome: '{resultado}'}})")
        await _esperar(
            nav, f"document.querySelector('.atualizacao')?.dataset.estado === '{resultado}'"
        )
        if resultado == "pronto":
            assert await nav.avaliar(
                "document.querySelector('.atualizacao [role=progressbar]')"
                ".getAttribute('aria-valuenow') === '100'"
            )
        else:
            assert await nav.avaliar(
                "document.querySelector('.atualizacao [role=progressbar]')"
                ".getAttribute('aria-valuenow') !== '100'"
            )
        if resultado == "falhou":
            assert await nav.avaliar(
                "document.querySelector('.atualizacao p').textContent.includes('<texto>')"
            )
            assert not await nav.avaliar("!!document.querySelector('.atualizacao texto')")
        # Fechar continua fechado no próximo batimento.
        await nav.avaliar("document.querySelector('[data-acao=atualizacao-fechar]').click()")
        await nav.avaliar("batimento()")
        assert not await nav.avaliar("!!document.querySelector('.atualizacao')")
        assert not nav.erros, nav.erros


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
@pytest.mark.parametrize("resultado", ["pronto", "falhou", "voltou"])
def test_andamento_da_atualizacao_permanece_ao_navegar_e_reiniciar(
    tmp_path: Path, resultado: str
) -> None:
    atualizacao = _AtualizacaoDeTeste(tmp_path / "andamento")
    extras: dict[str, Escrita] = {
        "ze/aplicar": atualizacao.aplicar,
        "teste/etapa": atualizacao.etapa,
    }
    with _painel(tmp_path, extras=extras, estado=atualizacao.estado) as (depuracao, endereco):
        asyncio.run(_ver_atualizacao(depuracao, endereco, resultado))


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
def test_sessoes_mostram_trava_sem_enviar_teclas_nem_repetir_as_recusadas(tmp_path: Path) -> None:
    atualizacao = _AtualizacaoDeTeste(tmp_path / "andamento")
    escritos: list[str] = []

    def escrever(dados: dict[str, Any]) -> dict[str, Any]:
        escritos.append(dados["dados"])
        return {}

    extras: dict[str, Escrita] = {
        "terminal/escrever": escrever,
        "teste/etapa": atualizacao.etapa,
        "ze/aplicar": atualizacao.aplicar,
    }

    async def conferir(depuracao: str, endereco: str) -> None:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#sessoes")
            await _esperar(nav, "!!document.querySelector('.item-sessao')")
            await nav.avaliar("document.querySelector('.item-sessao').click()")
            await _esperar(nav, "!!termId && !!document.querySelector('#reserva-sessoes')")
            assert await nav.avaliar("!term.options.disableStdin")
            await nav.avaliar("(async () => { escreverNoTerminal('antes'); await filaEscrita; })()")
            assert escritos == ["antes"]
            # Uma tecla em fila antes de Aplicar também precisa conferir a trava ao sair.
            await nav.avaliar(
                "window.liberarEscrita = null;"
                " filaEscrita = new Promise(ok => { window.liberarEscrita = ok; });"
                " escreverNoTerminal('em fila');"
            )
            await nav.avaliar("api('teste/etapa', {nome: 'aguardando'})")
            await nav.avaliar("batimento()")
            await nav.avaliar("(async () => { window.liberarEscrita(); await filaEscrita; })()")
            for etapa in ("aguardando", "testes_copia", "reiniciando"):
                if etapa != "aguardando":
                    await nav.avaliar(f"api('teste/etapa', {{nome: '{etapa}'}})")
                    await nav.avaliar("batimento()")
                assert await nav.avaliar("term.options.disableStdin")
                assert await nav.avaliar("!document.querySelector('#reserva-sessoes').hidden")
                assert await nav.avaliar("document.querySelector('[data-acao=anexar]').disabled")
                await nav.avaliar(
                    "(async () => { escreverNoTerminal('bloqueado'); await filaEscrita; })()"
                )
            assert escritos == ["antes"]
            await nav.avaliar("api('teste/etapa', {nome: 'falhou'})")
            await nav.avaliar("batimento()")
            assert await nav.avaliar("!term.options.disableStdin")
            assert await nav.avaliar("document.querySelector('#reserva-sessoes').hidden")
            await nav.avaliar(
                "(async () => { escreverNoTerminal('depois'); await filaEscrita; })()"
            )
            assert escritos == ["antes", "depois"]
            await nav.avaliar(
                "filaEscrita = new Promise(ok => { window.liberarEscrita = ok; });"
                " escreverNoTerminal('fila atrasada');"
            )
            await nav.avaliar("api('teste/etapa', {nome: 'aguardando'})")
            await nav.avaliar("batimento()")
            assert await nav.avaliar("term.options.disableStdin")
            await nav.avaliar("api('teste/etapa', {nome: 'cancelada'})")
            await nav.avaliar("batimento()")
            assert await nav.avaliar("!term.options.disableStdin")
            assert await nav.avaliar("document.querySelector('#reserva-sessoes').hidden")
            await nav.avaliar("(async () => { window.liberarEscrita(); await filaEscrita; })()")
            assert escritos == ["antes", "depois"]
            assert not nav.erros, nav.erros

    with _painel(tmp_path, extras=extras, estado=atualizacao.estado) as (depuracao, endereco):
        asyncio.run(conferir(depuracao, endereco))


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
def test_autodesenvolvimento_interrompe_troca_agente_e_permite_revisar(tmp_path: Path) -> None:
    respostas = json.loads(RESPOSTAS.read_text())
    sessao = respostas["escritas"]["sessao/ler"]
    sessao["sessao"].update(estado="trabalhando", limite=False, motor="claude")
    estado = respostas["leituras"]["estado"]
    estado["manutencao"]["ligada"] = False
    mudancas = respostas["escritas"]["ze/melhorias"]
    mudancas["protegidos"] = ["jarvis/oficina/manutencao.py"]
    chamadas: list[tuple[str, Any]] = []

    def fechar(dados: dict[str, Any]) -> dict[str, str]:
        chamadas.append(("interromper", dados))
        sessao["sessao"]["estado"] = "parada"
        return {"aviso": "Terminal fechado."}

    def trocar(dados: dict[str, Any]) -> dict[str, Any]:
        chamadas.append(("trocar", dados))
        sessao["sessao"].update(motor=dados["motor"], conta_id=dados["conta"], agente="Codex")
        return {**sessao["sessao"], "aviso": "Agente alterado."}

    def manutencao(dados: dict[str, Any]) -> dict[str, str]:
        estado["manutencao"]["ligada"] = dados["ligar"]
        return {"aviso": "Manutenção ligada."}

    def aplicar(dados: dict[str, Any]) -> dict[str, str]:
        chamadas.append(("aplicar", dados))
        return {"aviso": "Aplicando."}

    async def conferir(depuracao: str, endereco: str) -> None:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#melhorias")
            await _esperar(nav, "!!document.querySelector('#interromper-trabalho')")
            assert await nav.avaliar("document.querySelector('#ajustes-sessao button').disabled")
            await nav.avaliar("document.querySelector('#interromper-trabalho').click()")
            assert not chamadas  # a interrupção exige a confirmação
            await nav.avaliar(
                "document.querySelector('[data-acao=sessao-interromper-nao]').click()"
            )
            assert not chamadas
            await nav.avaliar("document.querySelector('#interromper-trabalho').click()")
            await nav.avaliar(
                "document.querySelector('[data-acao=sessao-interromper-sim]').click()"
            )
            await _esperar(nav, "!document.querySelector('#ajustes-sessao button').disabled")
            await nav.avaliar(
                "document.querySelector('[data-escolha=conta-sessao] button').click()"
            )
            await nav.avaliar("document.querySelector('[data-valor=\"codex|Exemplo\"]').click()")
            await _esperar(
                nav,
                "document.querySelector('[data-escolha=conta-sessao]').textContent.includes('Codex')",
            )
            assert chamadas[0][0] == "interromper" and chamadas[1][0] == "trocar"
            assert chamadas[1][1]["motor"] == "codex"
            assert chamadas[1][1]["continuar"] is False
            assert sessao["sessao"]["id"] == chamadas[1][1]["id"]
            # A página reabre no agente escolhido, sem criar outra sessão.
            await nav.avaliar("location.hash = '#inicio'")
            await _esperar(nav, "!document.querySelector('#terminal')")
            await nav.avaliar("location.hash = '#melhorias'")
            await _esperar(nav, "!!document.querySelector('#revisei')")
            assert await nav.avaliar(
                "document.querySelector('[data-escolha=conta-sessao]').textContent.includes('Codex')"
            )
            assert await nav.avaliar(
                "document.querySelector('[data-acao=melhorias-aplicar]').disabled"
            )
            await nav.avaliar(
                "document.querySelector('[data-acao=manutencao][data-ligar=true]').click()"
            )
            await _esperar(nav, "manut.ligada === true")
            await nav.avaliar("document.querySelector('#revisei').click()")
            await _esperar(nav, "!document.querySelector('[data-acao=melhorias-aplicar]').disabled")
            await nav.avaliar("document.querySelector('[data-acao=melhorias-aplicar]').click()")
            await _esperar(nav, "document.querySelector('.toast').textContent === 'Aplicando.'")
            assert chamadas[-1] == ("aplicar", {"revisei": True})
            assert not nav.erros, nav.erros

    extras: dict[str, Escrita] = {
        "sessao/ler": lambda _: copy.deepcopy(sessao),
        "ze/melhorias": lambda _: copy.deepcopy(mudancas),
        "terminal/fechar": fechar,
        "sessao/trocar": trocar,
        "ze/manutencao": manutencao,
        "ze/aplicar": aplicar,
    }
    with _painel(tmp_path, extras=extras, estado=lambda: copy.deepcopy(estado)) as (depuracao, url):
        asyncio.run(conferir(depuracao, url))


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
def test_escolher_conta_nao_reenvia_pedido_antigo_mesmo_com_alerta(tmp_path: Path) -> None:
    respostas = json.loads(RESPOSTAS.read_text())
    sessao = respostas["escritas"]["sessao/ler"]
    sessao["sessao"].update(estado="erro", limite=True, conta_id="claude:padrao")
    estado = respostas["leituras"]["estado"]
    estado["manutencao"]["ligada"] = False
    chamadas: list[dict[str, Any]] = []

    def trocar(dados: dict[str, Any]) -> dict[str, Any]:
        chamadas.append(dados)
        sessao["sessao"].update(
            limite=False,
            estado="parada",
            motor="codex",
            agente="Codex",
            conta_id=dados["conta"],
            conta="Exemplo",
        )
        return {**sessao["sessao"], "aviso": "Conta alterada."}

    async def conferir(depuracao: str, endereco: str) -> None:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#melhorias")
            await _esperar(nav, "!!document.querySelector('#limite-sessao .limite')")
            await nav.avaliar(
                "document.querySelector('[data-escolha=conta-sessao] button').click()"
            )
            await nav.avaliar("document.querySelector('[data-valor=\"codex|Exemplo\"]').click()")
            await _esperar(nav, "!document.querySelector('#limite-sessao .limite')")
            assert chamadas == [
                {
                    "id": sessao["sessao"]["id"],
                    "motor": "codex",
                    "conta": "Exemplo",
                    "continuar": False,
                }
            ]
            # Uma troca automática no backend atualiza o seletor e a faixa juntos.
            sessao["sessao"].update(
                conta_id="claude:padrao",
                conta="Padrão",
                motor="claude",
                agente="Claude",
                limite=True,
            )
            await nav.avaliar("acompanharSessao()")
            assert await nav.avaliar(
                "document.querySelector('[data-escolha=conta-sessao]').textContent.includes('Padrão')"
            )
            assert await nav.avaliar(
                "document.querySelector('#limite-sessao').textContent.includes('Padrão')"
            )
            assert not nav.erros

    with _painel(
        tmp_path,
        extras={"sessao/ler": lambda _: copy.deepcopy(sessao), "sessao/trocar": trocar},
        estado=lambda: copy.deepcopy(estado),
    ) as (depuracao, url):
        asyncio.run(conferir(depuracao, url))


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
@pytest.mark.parametrize("escolher", [False, True])
def test_unificacao_confirma_preserva_confirmacao_durante_poll_e_reabre_central(
    tmp_path: Path,
    escolher: bool,
) -> None:
    c: dict[str, Any] = {
        "sessao": "" if escolher else "sessao2",
        "estado": "disponivel",
        "aviso": "",
        "candidatas": [
            {"id": id_, "motor": motor, "conta": "", "branch": "ze/" + id_}
            for id_, motor in (("sessao2", "claude"), ("antiga1", "codex"), ("antiga2", "codex"))
        ],
        "arquivadas": [],
    }
    chamadas: list[dict[str, Any]] = []

    def unificar(dados: dict[str, Any]) -> dict[str, str]:
        chamadas.append(dados)
        c.update(sessao=dados["sessao"], estado="em_andamento", aviso="Unificando sessões.")
        return {"aviso": "Unificação iniciada."}

    async def conferir(depuracao: str, endereco: str) -> None:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#melhorias")
            await _esperar(nav, "!!document.querySelector('[data-acao=central-unificar]')")
            if escolher:
                assert await nav.avaliar("!document.querySelector('#terminal')")
                await nav.avaliar(
                    "const escolhaCentral = document.querySelector('#central-escolhida');"
                    " escolhaCentral.value = 'sessao2';"
                    " escolhaCentral.dispatchEvent(new Event('change'));"
                )
            else:
                await _esperar(nav, "!!document.querySelector('#terminal .xterm')")
            await nav.avaliar("document.querySelector('[data-acao=central-unificar]').click()")
            assert chamadas == []
            await nav.avaliar("acompanharCentral()")
            assert await nav.avaliar("!!document.querySelector('#centralizacao .confirmar')")
            await nav.avaliar("document.querySelector('[data-acao=confirmar-nao]').click()")
            assert chamadas == []
            await nav.avaliar("document.querySelector('[data-acao=central-unificar]').click()")
            await nav.avaliar("document.querySelector('[data-acao=confirmar-sim]').click()")
            await _esperar(nav, "window.unificandoSessoes === true")
            assert chamadas == [{"confirmado": True, "sessao": "sessao2"}]
            assert await nav.avaliar(
                "document.querySelector('[data-acao=central-unificar]').disabled"
            )
            if not escolher:
                assert await nav.avaliar("term.options.disableStdin")
                assert await nav.avaliar(
                    "document.querySelector('#reserva-sessoes strong').textContent"
                    " === 'Unificação em andamento'"
                )
            c.update(
                estado="concluida",
                aviso="Sessões unificadas. Histórico preservado.",
                candidatas=c["candidatas"][:1],
                arquivadas=["antiga1", "antiga2"],
            )
            await nav.avaliar("acompanharCentral()")
            await _esperar(nav, "!!document.querySelector('#terminal .xterm')")
            assert await nav.avaliar("sessaoAberta === 'sessao2' && !term.options.disableStdin")
            assert await nav.avaliar("document.querySelector('#centralizacao').hidden")
            assert await nav.avaliar("document.querySelector('#centralizacao').textContent === ''")
            assert not nav.erros, nav.erros

    extras: dict[str, Escrita] = {"ze/central": lambda _: copy.deepcopy(c), "ze/unificar": unificar}
    with _painel(tmp_path, extras=extras) as (depuracao, endereco):
        asyncio.run(conferir(depuracao, endereco))


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
def test_troca_de_aba_mostra_o_que_ja_tinha_sem_esperar_o_zé(tmp_path: Path) -> None:
    """Longe do servidor (VPS), cada resposta custa uma ida e volta: a aba que já foi aberta
    aparece na hora e se atualiza depois; uma gravação invalida o que estava guardado."""

    async def conferir(depuracao: str, endereco: str) -> None:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#inicio")
            await nav.avaliar('location.hash = "#modelos"')
            await asyncio.sleep(0.5)  # a mudança de endereço abre a página sozinha
            modelos_antes = await nav.avaliar('document.querySelector("#conteudo").innerText')
            await nav.avaliar('location.hash = "#inicio"')
            await asyncio.sleep(0.5)
            inicio = await nav.avaliar('document.querySelector("#conteudo").innerText') or ""
            assert not _quebrada(inicio) and inicio != modelos_antes
            # O Zé passa a responder em 2 s: a volta a "Modelos" não pode esperar por isso.
            await nav.avaliar(
                "(() => { const f = window.fetch; window.fetch = (...a) =>"
                " new Promise((ok) => setTimeout(() => ok(f(...a)), 2000)); })()"
            )
            await nav.avaliar('location.hash = "#modelos"')
            await asyncio.sleep(0.3)
            modelos = await nav.avaliar('document.querySelector("#conteudo").innerText') or ""
            assert modelos == modelos_antes, "a aba esperou pela resposta do Zé"
            # Uma gravação deixa as páginas guardadas velhas.
            await nav.avaliar(
                "cachePaginas.size > 0"
                " ? api('cerebro/escolher', {agente: 'claude'}).catch(() => 0) : 0"
            )
            assert await nav.avaliar("cachePaginas.size") == 0
            assert not nav.erros, nav.erros

    with _painel(tmp_path) as (depuracao, endereco):
        asyncio.run(conferir(depuracao, endereco))


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
def test_nova_sessao_comeca_no_agente_que_tem_conta_conectada(tmp_path: Path) -> None:
    """Na VPS só o Codex estava conectado, e a sessão nova abria no Claude."""
    respostas = json.loads(RESPOSTAS.read_text())
    contas = copy.deepcopy(respostas["leituras"]["contas"])
    contas["agentes"][0]["contas"][0]["logado"] = False  # o Claude, sem login

    async def conferir(depuracao: str, endereco: str) -> list[str]:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#sessoes")
            await nav.avaliar("formSessao()")
            await asyncio.sleep(0.5)
            marcados = await nav.avaliar(
                "[...document.querySelectorAll('[data-acao=ns-motor][aria-pressed=true]')]"
                ".map((b) => b.dataset.motor)"
            )
            assert not nav.erros, nav.erros
            return list(marcados)

    with _painel(tmp_path, trocas={"contas": contas}) as (depuracao, endereco):
        assert asyncio.run(conferir(depuracao, endereco)) == ["codex"]


def _conector_com_login(conectado: bool) -> dict[str, Any]:
    respostas = json.loads(RESPOSTAS.read_text())
    dados: dict[str, Any] = copy.deepcopy(respostas["leituras"]["conectores"])
    (notion,) = [c for c in dados["conectores"] if c["nome"] == "notion"]
    notion["conectado"] = conectado
    return dados


def test_entrar_no_conector_abre_o_login_no_clique_e_acompanha_ate_conectar(
    tmp_path: Path,
) -> None:
    """O "Abrir login" ficava escondido depois do Entrar (19/10/2026): agora a aba abre no
    clique, segue ao login quando o endereço chega, e o cartão vira Conectado sozinho."""
    entrou = threading.Event()
    pedidos: list[dict[str, Any]] = []

    def entrar(dados: dict[str, Any]) -> dict[str, Any]:
        pedidos.append(dados)
        return {"url": "https://login.exemplo.com/authorize?state=s"}

    async def conferir(depuracao: str, endereco: str) -> tuple[Any, str]:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#conectores")
            await nav.avaliar(
                "window.__abas = []; window.open = (...a) => {"
                " const aba = { location: { href: '' }, opener: 'painel', fechada: false,"
                " close() { this.fechada = true; } };"
                " window.__abas.push([a[0], aba]); return aba; }"
            )
            await nav.avaliar(
                "document.querySelector('[data-acao=conector-entrar][data-nome=notion]').click()"
            )
            await asyncio.sleep(0.5)
            abas = await nav.avaliar(
                "window.__abas.map(([u, a]) => [u, a.location.href, a.opener, a.fechada])"
            )
            entrou.set()  # o fornecedor devolveu o código ao Zé
            await asyncio.sleep(3)  # o painel pergunta a cada 2 s
            texto = await nav.avaliar('document.querySelector("#conteudo").innerText') or ""
            assert not nav.erros, nav.erros
            return abas, texto

    def lido() -> dict[str, Any]:
        return _conector_com_login(entrou.is_set())

    with _painel(
        tmp_path, extras={"conector/entrar": entrar}, leituras_vivas={"conectores": lido}
    ) as (depuracao, endereco):
        abas, texto = asyncio.run(conferir(depuracao, endereco))
    # Uma aba, aberta no clique (antes do endereço chegar), mandada ao login e sem o painel nela.
    assert abas == [["about:blank", "https://login.exemplo.com/authorize?state=s", None, False]]
    assert pedidos[0]["nome"] == "notion" and pedidos[0]["retorno"].endswith("/oauth/retorno")
    assert "Conectado" in texto and "Não conectado" not in texto


def test_entrar_com_a_aba_bloqueada_mostra_o_botao_abrir_login(tmp_path: Path) -> None:
    async def conferir(depuracao: str, endereco: str) -> tuple[str, str]:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#conectores")
            await nav.avaliar("window.open = () => null")  # o navegador bloqueou a aba
            await nav.avaliar(
                "document.querySelector('[data-acao=conector-entrar][data-nome=notion]').click()"
            )
            await asyncio.sleep(0.5)
            link = await nav.avaliar(
                "(() => { const a = document.querySelector('[data-login=notion] a.acao');"
                " return a ? a.href + '|' + getComputedStyle(a).borderRadius : ''; })()"
            )
            texto = await nav.avaliar('document.querySelector("#conteudo").innerText') or ""
            assert not nav.erros, nav.erros
            return link, texto

    with _painel(
        tmp_path,
        extras={"conector/entrar": lambda _d: {"url": "https://login.exemplo.com/a?s=1"}},
        leituras_vivas={"conectores": lambda: _conector_com_login(False)},
    ) as (depuracao, endereco):
        link, texto = asyncio.run(conferir(depuracao, endereco))
    # Com o estilo de botão (cantos arredondados): um link solto teria 0px.
    assert link == "https://login.exemplo.com/a?s=1|10px"
    assert "Abrir login" in texto and "bloqueou a nova aba" in texto


def test_servidor_sem_registro_automatico_abre_o_app_proprio_e_guarda_o_client_id(
    tmp_path: Path,
) -> None:
    enviados: list[dict[str, Any]] = []

    def entrar(_dados: dict[str, Any]) -> dict[str, Any]:
        raise PedidoInvalido("o servidor não aceita o registro automático: guarde o app próprio")

    def guardar(dados: dict[str, Any]) -> dict[str, Any]:
        enviados.append(dados)
        return {}

    async def conferir(depuracao: str, endereco: str) -> tuple[bool, bool]:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#conectores")
            await nav.avaliar("window.open = () => null")
            fechado = await nav.avaliar("document.querySelector('[data-detalhes=notion]').open")
            await nav.avaliar(
                "document.querySelector('[data-acao=conector-entrar][data-nome=notion]').click()"
            )
            await asyncio.sleep(0.6)
            aberto = await nav.avaliar("document.querySelector('[data-detalhes=notion]').open")
            await nav.avaliar(
                "document.querySelector('[data-cliente-id=notion]').value = 'meu-app';"
                "document.querySelector('[data-cliente-segredo=notion]').value = 's3gr3d0';"
                "document.querySelector('[data-acao=conector-cliente][data-nome=notion]').click()"
            )
            await asyncio.sleep(0.6)
            assert not nav.erros, nav.erros
            return bool(fechado), bool(aberto)

    with _painel(
        tmp_path,
        extras={"conector/entrar": entrar, "conector/cliente": guardar},
        leituras_vivas={"conectores": lambda: _conector_com_login(False)},
    ) as (depuracao, endereco):
        fechado, aberto = asyncio.run(conferir(depuracao, endereco))
    assert (fechado, aberto) == (False, True)  # o erro leva ao lugar de resolver
    assert enviados == [{"nome": "notion", "client_id": "meu-app", "client_secret": "s3gr3d0"}]


def test_editar_conector_abre_preenchido_e_mantem_as_permissoes(tmp_path: Path) -> None:
    """O cartão só deixava remover (19/10/2026): Editar abre o formulário com o que está
    gravado, o nome fixo, e Salvar manda as permissões que já existiam."""
    salvos: list[dict[str, Any]] = []

    def salvar(dados: dict[str, Any]) -> dict[str, Any]:
        salvos.append(dados)
        return {}

    async def conferir(depuracao: str, endereco: str) -> list[Any]:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#conectores")
            await nav.avaliar(
                "document.querySelector('[data-acao=conector-editar][data-nome=crm]').click()"
            )
            await asyncio.sleep(0.3)
            campos = await nav.avaliar(
                "['cx-nome','cx-url','cx-cabecalhos'].map("
                "(i) => document.getElementById(i).value)"
                ".concat([document.getElementById('cx-nome').readOnly,"
                " document.querySelector('#form-conector h2').textContent])"
            )
            await nav.avaliar(
                "document.getElementById('cx-url').value = 'https://n8n.exemplo.com/mcp-server/http';"
                "document.querySelector('[data-acao=cx-salvar]').click()"
            )
            await asyncio.sleep(0.6)
            assert not nav.erros, nav.erros
            return list(campos)

    with _painel(tmp_path, extras={"conector/salvar": salvar}) as (depuracao, endereco):
        campos = asyncio.run(conferir(depuracao, endereco))
    assert campos == [
        "crm",
        "https://mcp.exemplo.com/mcp",
        "Authorization: CRM_TOKEN",
        True,
        "Editar crm",
    ]
    (enviado,) = salvos
    assert enviado["url"] == "https://n8n.exemplo.com/mcp-server/http"
    assert enviado["cabecalhos"] == {"Authorization": "CRM_TOKEN"}
    assert (enviado["livres"], enviado["bloqueadas"], enviado["projetos"]) == (
        ["buscar_contatos"],
        [],
        ["loja"],
    )


def test_cabecalho_fora_do_formato_avisa_e_nao_salva_calado(tmp_path: Path) -> None:
    """Uma linha de cabeçalho sem "Nome: VARIAVEL" sumia sem aviso (19/10/2026): o conector do
    n8n foi salvo sem o Authorization e o teste dava 401."""
    salvos: list[dict[str, Any]] = []

    def salvar(dados: dict[str, Any]) -> dict[str, Any]:
        salvos.append(dados)
        return {}

    async def conferir(depuracao: str, endereco: str) -> str:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#conectores")
            await nav.avaliar(
                "document.querySelector('[data-acao=conector-novo]').click();"
                "document.querySelector('[data-acao=cx-tipo][data-tipo=http]').click();"
                "document.getElementById('cx-nome').value = 'n8n';"
                "document.getElementById('cx-url').value = 'https://n8n.exemplo.com/mcp-server/http';"
                "document.getElementById('cx-cabecalhos').value = 'Authorization N8N_AUTH';"
                "document.querySelector('[data-acao=cx-salvar]').click()"
            )
            await asyncio.sleep(0.5)
            texto = await nav.avaliar("document.body.innerText") or ""
            await nav.avaliar(
                "document.getElementById('cx-cabecalhos').value = 'Authorization: N8N_AUTH';"
                "document.querySelector('[data-acao=cx-salvar]').click()"
            )
            await asyncio.sleep(0.5)
            return str(texto)

    with _painel(tmp_path, extras={"conector/salvar": salvar}) as (depuracao, endereco):
        texto = asyncio.run(conferir(depuracao, endereco))
    assert "Cabeçalho inválido" in texto
    (enviado,) = salvos  # só a segunda tentativa, no formato certo
    assert enviado["cabecalhos"] == {"Authorization": "N8N_AUTH"}


def test_colar_a_configuracao_salva_testa_e_mostra_o_resultado(tmp_path: Path) -> None:
    """O jeito comum (19/10/2026): colar o JSON que o serviço dá, sem preencher campos."""
    importados: list[dict[str, Any]] = []
    colado = '{"mcpServers": {"crm": {"type": "http", "url": "https://mcp.exemplo.com/mcp"}}}'

    def importar(dados: dict[str, Any]) -> dict[str, Any]:
        importados.append(dados)
        respostas = json.loads(RESPOSTAS.read_text())
        ferramentas = [{"nome": "buscar_contatos", "descricao": "Busca"}]
        teste = {"nome": "crm", "ok": True, "ms": 5, "ferramentas": ferramentas}
        return {**respostas["leituras"]["conectores"], "testes": [teste]}

    async def conferir(depuracao: str, endereco: str) -> tuple[str, str]:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#conectores")
            await nav.avaliar(
                "document.querySelector('[data-acao=conector-novo]').click();"
                f"document.getElementById('cx-colar').value = {json.dumps(colado)};"
                "document.getElementById('cx-nome').value = 'crm';"
                "document.querySelector('[data-acao=cx-salvar]').click()"
            )
            await asyncio.sleep(0.8)
            cartao = await nav.avaliar("document.querySelector('[data-resultado=crm]').textContent")
            texto = await nav.avaliar("document.body.innerText") or ""
            assert not nav.erros, nav.erros
            return str(cartao), str(texto)

    with _painel(tmp_path, extras={"conector/importar": importar}) as (depuracao, endereco):
        cartao, texto = asyncio.run(conferir(depuracao, endereco))
    assert importados == [{"texto": colado, "nome": "crm", "novo": True}]
    assert cartao == "1 ferramenta" and "crm: 1 ferramenta." in texto
    assert "buscar_contatos" in texto  # as permissões abrem sem outro clique


def test_sessao_escolhe_os_conectores_do_projeto(tmp_path: Path) -> None:
    """O seletor na sessão (19/10/2026): marcar o n8n do cliente ali mesmo, ver onde mais ele
    está, e salvar reabre o agente com a conversa."""
    salvos: list[dict[str, Any]] = []
    lista = {
        "conectores": [
            {"nome": "docs", "tipo": "http", "marcado": True, "todos": True, "editavel": False,
             "outros": []},
            {"nome": "n8n-joao", "tipo": "http", "marcado": False, "todos": False,
             "editavel": True, "outros": ["loja-do-joao"]},
        ]
    }  # fmt: skip

    def salvar(dados: dict[str, Any]) -> dict[str, Any]:
        salvos.append(dados)
        respostas = json.loads(RESPOSTAS.read_text())
        return {**respostas["escritas"]["sessao/ler"]["sessao"], "aviso": "Conectores: docs."}

    async def conferir(depuracao: str, endereco: str) -> tuple[str, str]:
        async with websockets.connect(depuracao, max_size=None) as ws:
            nav = _Navegador(ws)
            await _carregar(nav, endereco + "#sessoes")
            await _esperar(nav, "!!document.querySelector('.item-sessao')")
            await nav.avaliar("document.querySelector('.item-sessao').click()")
            await _esperar(nav, "!!document.querySelector('[data-acao=sessao-conectores]')")
            await nav.avaliar("document.querySelector('[data-acao=sessao-conectores]').click()")
            await _esperar(nav, "!!document.querySelector('[data-conector-sessao=n8n-joao]')")
            texto = await nav.avaliar("document.getElementById('conectores-da-sessao').innerText")
            travado = await nav.avaliar(
                "document.querySelector('[data-conector-sessao=docs]').disabled"
            )
            await nav.avaliar(
                "document.querySelector('[data-conector-sessao=n8n-joao]').click();"
                "document.querySelector('[data-acao=sessao-conectores-salvar]').click()"
            )
            await asyncio.sleep(0.6)
            assert not nav.erros, nav.erros
            return str(texto), str(travado)

    with _painel(
        tmp_path,
        extras={"sessao/conectores": lambda _d: lista, "sessao/conectores/salvar": salvar},
    ) as (depuracao, endereco):
        texto, travado = asyncio.run(conferir(depuracao, endereco))
    assert "Também em: loja-do-joao" in texto and "Todos os projetos" in texto
    assert travado == "True"  # o de todos os projetos não sai por uma sessão
    assert salvos == [{"id": "sessao1", "nomes": ["docs", "n8n-joao"]}]
