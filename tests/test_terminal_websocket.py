"""A entrada do terminal usa um WebSocket autenticado e preserva a ordem."""

import http.client
import json
import threading
from typing import Any

import pytest
from websockets.exceptions import ConnectionClosed, InvalidHandshake
from websockets.sync.client import connect
from websockets.typing import Origin

from jarvis.portal.servidor import Portal


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
            assert json.loads(ws.recv(timeout=2)) == {"tipo": "pronto"}
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
