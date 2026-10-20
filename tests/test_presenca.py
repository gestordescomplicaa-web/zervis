"""Presença pelo Hyprland, com as linhas reais vistas na Prova 3 (06/10/2026)."""

import os
import socket
import threading
import time
from pathlib import Path

from zervis.presenca.hyprland import CLASSE, Janelas, MonitorPresenca, pastas_de_instancia

ABRIU = f"openwindow>>59fe8abbff90,1,{CLASSE},127.0.0.1_/stage.html"
FECHOU = "closewindow>>59fe8abbff90"


def test_abre_e_fecha_pela_classe() -> None:
    j = Janelas()
    j.evento("windowtitlev2>>59fe8abbff90,127.0.0.1_/stage.html")
    assert not j.aberta
    j.evento(ABRIU)
    assert j.aberta
    j.evento("movewindowv2>>59fe8abbff90,9,9")
    assert j.aberta  # em outra área continua aberta
    j.evento(FECHOU)
    assert not j.aberta


def test_outra_janela_do_chromium_nao_conta() -> None:
    j = Janelas()
    j.evento("openwindow>>59fe8aa35270,2,chromium,(5) WhatsApp Business - Chromium")
    assert not j.aberta
    j.evento(ABRIU)
    j.evento("closewindow>>59fe8aa35270")
    assert j.aberta


def test_titulo_com_virgulas_nao_quebra() -> None:
    j = Janelas()
    j.evento(f"openwindow>>abc,1,{CLASSE},barehands, versão 2, teste")
    assert j.aberta


def test_conciliar_usa_o_hyprctl_sem_o_prefixo_0x() -> None:
    j = Janelas()
    j.conciliar(
        [{"address": "0x59fe8abbff90", "class": CLASSE}, {"address": "0x1", "class": "orca"}]
    )
    assert j.enderecos == {"59fe8abbff90"}
    j.evento(FECHOU)
    assert not j.aberta


def test_instancia_do_ambiente_primeiro_e_depois_a_mais_nova(tmp_path: Path) -> None:
    for nome, idade in (("velha", 100), ("nova", 10), ("atual", 50)):
        (tmp_path / nome).mkdir()
        os.utime(tmp_path / nome, (time.time() - idade,) * 2)
    assert [p.name for p in pastas_de_instancia(tmp_path, "atual")] == ["atual", "nova", "velha"]
    assert pastas_de_instancia(tmp_path / "nada", None) == []


def test_monitor_segue_os_eventos_do_socket(tmp_path: Path) -> None:
    pasta = tmp_path / "inst"
    pasta.mkdir()
    servidor = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    servidor.bind(str(pasta / ".socket2.sock"))
    servidor.listen(1)
    mudancas: list[bool] = []
    parar = threading.Event()
    monitor = MonitorPresenca(mudancas.append, parar, base=tmp_path)
    monitor.assinatura = "inst"
    monitor._hyprctl = lambda: []  # type: ignore[method-assign]
    monitor.start()
    conexao, _ = servidor.accept()
    with conexao:
        conexao.sendall(f"{ABRIU}\n".encode())
        _esperar(lambda: mudancas == [False, True])
        conexao.sendall(f"{FECHOU}\n".encode())
        _esperar(lambda: mudancas == [False, True, False])
    parar.set()
    monitor.join(timeout=3)
    servidor.close()
    assert mudancas == [False, True, False]


def test_sem_hyprland_fica_ausente(tmp_path: Path) -> None:
    mudancas: list[bool] = []
    parar = threading.Event()
    monitor = MonitorPresenca(mudancas.append, parar, base=tmp_path)
    monitor._hyprctl = lambda: None  # type: ignore[method-assign]
    monitor.start()
    _esperar(lambda: mudancas == [False])
    parar.set()
    monitor.join(timeout=3)
    assert mudancas == [False]


def _esperar(condicao: object, limite: float = 3.0) -> None:
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        if condicao():  # type: ignore[operator]
            return
        time.sleep(0.02)
    raise AssertionError("condição não ocorreu a tempo")


def test_a_janela_do_painel_tambem_e_a_do_ze() -> None:
    """09/10/2026: o modo imersivo passou a morar numa aba do painel."""
    from zervis.presenca.hyprland import CLASSE_PAINEL

    j = Janelas()
    j.evento(f"openwindow>>7a01,1,{CLASSE_PAINEL},Zé — painel")
    assert j.aberta
    j.conciliar([{"address": "0x7a01", "class": CLASSE_PAINEL}, {"address": "0x1", "class": "x"}])
    assert j.enderecos == {"7a01"}
