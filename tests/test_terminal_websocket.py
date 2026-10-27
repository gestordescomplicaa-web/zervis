"""O terminal das sessões usa um WebSocket autenticado: as teclas vão em ordem e a saída volta
assim que sai (sem uma viagem nova por pedaço, como na leitura HTTP)."""

import base64
import http.client
import json
import struct
import threading
import time
from typing import Any

import pytest
from websockets.exceptions import ConnectionClosed, InvalidHandshake
from websockets.sync.client import connect
from websockets.typing import Origin

from zervis.portal.servidor import Portal


def _url(portal: Portal) -> str:
    return f"ws://127.0.0.1:{portal.porta}/api/terminal/ws"


def _origem(portal: Portal) -> Origin:
    return Origin(f"http://127.0.0.1:{portal.porta}")


def test_entrada_persistente_preserva_a_ordem() -> None:
    recebidas: list[dict[str, Any]] = []
    chegaram = threading.Event()

    def escrever(dados: dict[str, Any]) -> None:
        recebidas.append(dados)
        if len(recebidas) == 3:
            chegaram.set()

    portal = Portal({}, {}, porta=0, entrada_terminal=escrever)
    portal.iniciar()
    try:
        with connect(_url(portal), origin=_origem(portal)) as ws:
            ws.send(json.dumps({"id": "sessao-teste", "token": portal.token}))
            assert json.loads(ws.recv(timeout=2)) == {"tipo": "pronto", "saida": False}
            for tecla in ("c", "od", "ex\r"):
                ws.send(tecla)
            assert chegaram.wait(2)
        assert recebidas == [
            {"id": "sessao-teste", "dados": "c"},
            {"id": "sessao-teste", "dados": "od"},
            {"id": "sessao-teste", "dados": "ex\r"},
        ]
    finally:
        portal.parar()


def test_terminal_recusa_origem_e_token_invalidos() -> None:
    recebidas: list[dict[str, Any]] = []
    portal = Portal({}, {}, porta=0, entrada_terminal=recebidas.append)
    portal.iniciar()
    try:
        with pytest.raises(InvalidHandshake):
            connect(_url(portal), origin=Origin("https://site-malicioso.example"))
        with connect(_url(portal), origin=_origem(portal)) as ws:
            ws.send(json.dumps({"id": "sessao-teste", "token": "incorreto"}))
            with pytest.raises(ConnectionClosed):
                ws.recv(timeout=2)
        assert recebidas == []
    finally:
        portal.parar()


def test_terminal_exige_acesso_remoto() -> None:
    class AcessoFalso:
        def valido(self, _cookie: str) -> bool:
            return False

    portal = Portal({}, {}, porta=0, acesso=AcessoFalso(), entrada_terminal=lambda _: None)  # type: ignore[arg-type]
    portal.permitir("ze.exemplo")
    portal.iniciar()
    try:
        conexao = http.client.HTTPConnection("127.0.0.1", portal.porta, timeout=2)
        conexao.request(
            "GET",
            "/api/terminal/ws",
            headers={
                "Host": "ze.exemplo",
                "Origin": "https://ze.exemplo",
                "X-Forwarded-For": "198.51.100.8",
            },
        )
        resposta = conexao.getresponse()
        resposta.read()
        conexao.close()
        assert resposta.status == 403
    finally:
        portal.parar()


class SaidaFalsa:
    """O `terminal/ler` das sessões: devolve, uma a uma, as respostas preparadas."""

    def __init__(self, respostas: list[dict[str, Any]]) -> None:
        self.respostas = respostas
        self.pedidos: list[dict[str, Any]] = []
        self.acabou = threading.Event()

    def __call__(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.pedidos.append(dict(dados))
        if not self.respostas:
            self.acabou.set()
            time.sleep(0.05)
            return {"posicao": dados["desde"], "dados": "", "vivo": True}
        return self.respostas.pop(0)


def _b64(dados: bytes) -> str:
    return base64.b64encode(dados).decode()


def _quadro(mensagem: str | bytes) -> tuple[int, bytes]:
    assert isinstance(mensagem, bytes), mensagem
    return struct.unpack("!Q", mensagem[:8])[0], mensagem[8:]


def test_a_saida_vai_pelo_websocket_assim_que_sai() -> None:
    saida = SaidaFalsa([
        {"posicao": 103, "dados": _b64(b"ola"), "vivo": True, "geracao": 7},
        {"posicao": 105, "dados": _b64(b"\r\n"), "vivo": True, "geracao": 7},
        {"posicao": 105, "dados": "", "vivo": False, "geracao": 7, "trocando": True},
        {"posicao": 4, "dados": _b64(b"nova"), "vivo": True, "geracao": 9, "reiniciado": True},
        {"posicao": 4, "dados": "", "vivo": False, "geracao": 9},
    ])  # fmt: skip
    portal = Portal({}, {}, porta=0, entrada_terminal=lambda _: None, saida_terminal=saida)
    portal.iniciar()
    try:
        with connect(_url(portal), origin=_origem(portal)) as ws:
            ws.send(json.dumps({"id": "s1", "token": portal.token, "saida": True, "desde": 100}))
            assert json.loads(ws.recv(timeout=2)) == {"tipo": "pronto", "saida": True}
            assert _quadro(ws.recv(timeout=2)) == (103, b"ola")
            assert _quadro(ws.recv(timeout=2)) == (105, b"\r\n")
            # A conta trocou: o terminal novo começa do zero, e o navegador limpa a tela antes.
            assert json.loads(ws.recv(timeout=2)) == {"tipo": "reiniciado"}
            assert _quadro(ws.recv(timeout=2)) == (4, b"nova")
            assert json.loads(ws.recv(timeout=2)) == {"tipo": "fechado"}
        # Cada leitura continua de onde a outra parou, com a geração do terminal que viu.
        assert [(p["desde"], p["geracao"]) for p in saida.pedidos] == [
            (100, 0), (103, 7), (105, 7), (105, 7), (4, 9),
        ]  # fmt: skip
        assert all(p["id"] == "s1" for p in saida.pedidos)
    finally:
        portal.parar()


def test_sem_pedir_a_saida_o_websocket_so_leva_as_teclas() -> None:
    saida = SaidaFalsa([])
    portal = Portal({}, {}, porta=0, entrada_terminal=lambda _: None, saida_terminal=saida)
    portal.iniciar()
    try:
        with connect(_url(portal), origin=_origem(portal)) as ws:
            ws.send(json.dumps({"id": "s1", "token": portal.token}))
            assert json.loads(ws.recv(timeout=2)) == {"tipo": "pronto", "saida": False}
            with pytest.raises(TimeoutError):
                ws.recv(timeout=0.3)
        assert saida.pedidos == []
    finally:
        portal.parar()


def test_ao_fechar_a_conexao_a_leitura_para() -> None:
    saida = SaidaFalsa([])
    portal = Portal({}, {}, porta=0, entrada_terminal=lambda _: None, saida_terminal=saida)
    portal.iniciar()
    try:
        with connect(_url(portal), origin=_origem(portal)) as ws:
            ws.send(json.dumps({"id": "s1", "token": portal.token, "saida": True, "desde": 0}))
            ws.recv(timeout=2)
            assert saida.acabou.wait(2)
        time.sleep(0.3)
        antes = len(saida.pedidos)
        time.sleep(0.3)
        assert len(saida.pedidos) == antes  # nenhuma leitura presa depois de fechar
    finally:
        portal.parar()
