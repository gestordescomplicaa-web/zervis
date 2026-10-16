"""A voz pelo navegador dentro do HTTPS do painel (roteiro, passo 4.2): WebSocket e áudio."""

import json
import threading
import time
from typing import Any

import numpy as np
import pytest
from websockets.exceptions import InvalidHandshake
from websockets.sync.client import connect
from websockets.typing import Origin

from jarvis.portal.servidor import Portal
from jarvis.transporte.navegador import BYTES_QUADRO, TocadorNavegador, VozNavegador, reamostrar
from jarvis.transporte.websocket import Conexao


class Eco:
    """O Zé falso: devolve o primeiro quadro recebido e guarda tudo."""

    def __init__(self) -> None:
        self.quadros: list[bytes] = []
        self.taxas: list[int] = []

    def __call__(self, conexao: Conexao, taxa: int) -> None:
        self.taxas.append(taxa)
        voz = VozNavegador(conexao, taxa)

        def receber(q: bytes) -> None:
            self.quadros.append(q)
            if len(self.quadros) == 1:
                conexao.binario(q)

        voz.ouvir(receber)


@pytest.fixture
def portal() -> Any:
    eco = Eco()
    p = Portal({}, {}, porta=0, voz=eco)
    p.iniciar()
    yield p, eco
    p.parar()


def _url(p: Portal) -> str:
    return f"ws://127.0.0.1:{p.porta}/api/voz/ws"


def test_audio_vai_em_quadros_de_80_ms_e_volta(portal: Any) -> None:
    p, eco = portal
    with connect(_url(p), origin=Origin(f"http://127.0.0.1:{p.porta}")) as ws:
        ws.send(json.dumps({"token": p.token, "taxa": 16000}))
        ws.send(b"\1\0" * 1000)  # pedaço menor que um quadro: espera o resto
        ws.send(b"\1\0" * 1000)
        assert ws.recv(timeout=5) == b"\1\0" * (BYTES_QUADRO // 2)
    for _ in range(50):
        if eco.quadros:
            break
        time.sleep(0.02)
    assert eco.taxas == [16000] and all(len(q) == BYTES_QUADRO for q in eco.quadros)


def test_outra_origem_e_codigo_errado_nao_abrem_a_voz(portal: Any) -> None:
    p, eco = portal
    with pytest.raises(InvalidHandshake):  # o painel responde 403
        connect(_url(p), origin=Origin("https://malicioso.com"))
    with connect(_url(p), origin=Origin(f"http://127.0.0.1:{p.porta}")) as ws:
        ws.send(json.dumps({"token": "errado", "taxa": 16000}))
        with pytest.raises(Exception):  # noqa: B017 (o servidor fecha: qualquer erro de conexão)
            ws.recv(timeout=5)
    assert eco.taxas == []


def test_reamostra_o_navegador_que_nao_aceitou_16_khz() -> None:
    pcm = (np.sin(np.linspace(0, 100, 48000)) * 10000).astype("<i2").tobytes()
    assert len(reamostrar(pcm, 48000)) == 16000 * 2
    assert reamostrar(pcm, 16000) == pcm


class ConexaoFalsa:
    def __init__(self) -> None:
        self.aberta = True
        self.textos: list[dict[str, Any]] = []
        self.bytes = 0

    def texto(self, m: str) -> None:
        self.textos.append(json.loads(m))

    def binario(self, d: bytes) -> None:
        self.bytes += len(d)


def test_tocador_anuncia_a_fala_vai_no_ritmo_e_interrompe() -> None:
    con = ConexaoFalsa()
    voz = VozNavegador(con)  # type: ignore[arg-type]
    t = TocadorNavegador(voz, 22050)
    meio_segundo = np.zeros(11025, dtype="<f4").tobytes()
    inicio = time.monotonic()
    for _ in range(3):  # 1,5 s de fala: vai no máximo 0,5 s à frente
        t.write(meio_segundo)
    assert time.monotonic() - inicio >= 0.9
    t.close()
    assert con.textos[0] == {"tipo": "voz", "taxa": 22050} and con.textos[-1] == {"tipo": "fim"}
    assert con.bytes == 3 * 11025 * 2
    t2 = TocadorNavegador(voz, 22050)
    threading.Timer(0.1, t2.kill).start()
    with pytest.raises(BrokenPipeError):
        for _ in range(10):
            t2.write(meio_segundo)
    assert con.textos[-1] == {"tipo": "parar"} and t2.wait() == -9


def test_buraco_no_audio_do_navegador_vai_para_o_registro(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """O navegador manda um quadro a cada 80 ms; meio segundo sem nenhum é rede ou tela apagada."""
    from jarvis.transporte.websocket import BINARIO, FechouErro

    quadro = bytes(BYTES_QUADRO)
    chegadas = iter([(BINARIO, quadro), (BINARIO, quadro), (BINARIO, quadro)])
    esperas = iter([0.0, 0.7, 0.0])

    class Conexao:
        def receber(self) -> tuple[int, bytes]:
            time.sleep(next(esperas, 0.0))
            try:
                return next(chegadas)
            except StopIteration:
                raise FechouErro from None

    quadros: list[bytes] = []
    with caplog.at_level("WARNING"):
        VozNavegador(Conexao()).ouvir(quadros.append)  # type: ignore[arg-type]
    assert len(quadros) == 3
    avisos = [r.getMessage() for r in caplog.records if "sem áudio" in r.getMessage()]
    assert len(avisos) == 1 and "0.7 s" in avisos[0]
