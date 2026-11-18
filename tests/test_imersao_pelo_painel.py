"""A Imersão pelo painel (ADR 0100): de outro aparelho, só depois de entrar; o pedido chega ao
palco como se fosse do PC, sem cookie nem origem; a câmera e as mãos da máquina não passam."""

import http.client
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from zervis.portal.senha import Acesso
from zervis.portal.servidor import COOKIE, Portal

HOST = "ze.trycloudflare.com"
FORA = {"Cf-Connecting-Ip": "203.0.113.7"}


class PalcoFalso:
    """O servidor do palco: guarda o que recebeu e responde como ele."""

    def __init__(self) -> None:
        self.pedidos: list[dict[str, Any]] = []
        palco = self

        class Tratador(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                return None

            def _responder(self, corpo: bytes) -> None:
                palco.pedidos.append(
                    {"metodo": self.command, "alvo": self.path, "cab": dict(self.headers.items()),
                     "corpo": corpo}
                )  # fmt: skip
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("X-Mirror", "0")
                self.send_header("Content-Length", str(len(b"<html>palco</html>")))
                self.end_headers()
                self.wfile.write(b"<html>palco</html>")

            def do_GET(self) -> None:
                self._responder(b"")

            def do_POST(self) -> None:
                self._responder(self.rfile.read(int(self.headers.get("Content-Length") or 0)))

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Tratador)
        self.porta = self.http.server_port
        threading.Thread(target=self.http.serve_forever, daemon=True).start()


@pytest.fixture
def painel(tmp_path: Path) -> Iterator[tuple[Portal, PalcoFalso, str]]:
    palco = PalcoFalso()
    acesso = Acesso(tmp_path / "painel.json", tmp_path / "acessos.json")
    acesso.definir("uma senha boa")
    cookie, _ = acesso.entrar("uma senha boa", lembrar=False)
    p = Portal({}, {}, porta=0, acesso=acesso, servidor=True, imersivo=palco.porta)
    p.permitir(HOST)
    p.iniciar()
    yield p, palco, f"{COOKIE}={cookie}"
    p.parar()
    palco.http.shutdown()


def _pedir(
    p: Portal, metodo: str, caminho: str, cab: dict[str, str], corpo: bytes = b""
) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", p.porta, timeout=5)
    conn.request(metodo, caminho, body=corpo or None, headers={"Host": HOST, **FORA, **cab})
    r = conn.getresponse()
    resposta = (r.status, dict(r.getheaders()), r.read())
    conn.close()
    return resposta


def test_de_fora_so_depois_de_entrar(painel: Any) -> None:
    p, palco, _ = painel
    status, cab, _ = _pedir(p, "GET", "/imersao/stage.html?camera=0", {})
    assert status == 303 and cab["Location"] == "/entrar"
    assert _pedir(p, "POST", "/imersao/teclado", {}, b"{}")[0] == 401
    assert palco.pedidos == []


def test_o_palco_recebe_como_do_pc_sem_cookie_nem_origem(painel: Any) -> None:
    p, palco, cookie = painel
    entrou = {"Cookie": cookie, "Origin": f"https://{HOST}", "Referer": f"https://{HOST}/"}
    status, cab, corpo = _pedir(p, "GET", "/imersao/stage.html?camera=0", entrou)
    assert status == 200 and corpo == b"<html>palco</html>"
    assert cab["X-Frame-Options"] == "SAMEORIGIN" and cab["X-Mirror"] == "0"
    status, _, _ = _pedir(
        p, "POST", "/imersao/teclado", {**entrou, "X-Ze-Token": "do-palco"}, b'{"texto": "oi"}'
    )
    assert status == 200
    pagina, teclado = palco.pedidos
    assert pagina["alvo"] == "/stage.html?camera=0"
    assert teclado["alvo"] == "/teclado" and teclado["corpo"] == b'{"texto": "oi"}'
    assert teclado["cab"]["X-Ze-Token"] == "do-palco"
    for pedido in palco.pedidos:
        assert pedido["cab"]["Host"] == f"127.0.0.1:{palco.porta}"
        assert not {"Cookie", "Origin", "Referer", "Cf-Connecting-Ip"} & set(pedido["cab"])


def test_a_camera_e_gravar_as_maos_da_maquina_nao_passam(painel: Any) -> None:
    p, palco, cookie = painel
    for caminho in ("/imersao/camera/ajustar", "/imersao/maos/perfil"):
        assert _pedir(p, "POST", caminho, {"Cookie": cookie}, b"{}")[0] == 403
    assert _pedir(p, "GET", "/imersao/camera/info?nome=x", {"Cookie": cookie})[0] == 403
    assert palco.pedidos == []
    assert _pedir(p, "GET", "/imersao/maos/perfil", {"Cookie": cookie})[0] == 200  # só ler


def test_sem_o_palco_a_resposta_e_clara(painel: Any) -> None:
    p, palco, cookie = painel
    palco.http.shutdown()
    palco.http.server_close()
    status, _, corpo = _pedir(p, "GET", "/imersao/stage.html", {"Cookie": cookie})
    assert status == 502 and "Imersão indisponível" in corpo.decode()
