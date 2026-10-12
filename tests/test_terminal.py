"""O terminal das sessões: um programa real num PTY, lido a partir de uma posição."""

import contextlib
import os
import signal
import sys
import threading
import time
from pathlib import Path

import pytest

from jarvis.oficina.terminal import Terminal

# O Python avisa de fork com threads; o filho do Terminal só chama chdir e execve.
pytestmark = pytest.mark.filterwarnings(
    "ignore:This process .* is multi-threaded:DeprecationWarning"
)


def _ler_ate(t: Terminal, trecho: bytes) -> bytes:
    pos, visto = 0, b""
    for _ in range(50):
        pos, dados, vivo = t.ler(pos, espera_s=0.2)
        visto += dados
        if trecho in visto or not vivo:
            break
    return visto


def test_le_escreve_e_avisa_a_saida(tmp_path: Path) -> None:
    saiu = threading.Event()
    codigos: list[int] = []

    def ao_sair(codigo: int) -> None:
        codigos.append(codigo)
        saiu.set()

    t = Terminal(
        ["sh", "-c", 'printf "pronto\\n"; read x; echo "eco:$x"; exit 3'], tmp_path, {}, ao_sair
    )
    assert b"pronto" in _ler_ate(t, b"pronto")
    t.escrever(b"caju\r")
    assert b"eco:caju" in _ler_ate(t, b"eco:caju")
    assert saiu.wait(5)
    assert codigos == [3]
    assert not t.vivo
    t.escrever(b"depois")  # terminal fechado: ignora, sem erro


def test_colar_entrega_o_pedido_inteiro(tmp_path: Path) -> None:
    t = Terminal(["sh", "-c", 'read x; echo "fim:$x"'], tmp_path, {})
    t.colar("uma linha só")
    visto = _ler_ate(t, b"fim:")
    assert b"uma linha s" in visto
    t.encerrar()


def test_buffer_circular_mantem_o_fim(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("jarvis.oficina.terminal.BUFFER", 1024)
    t = Terminal(["sh", "-c", "head -c 5000 /dev/zero | tr '\\0' a; printf FIM"], tmp_path, {})
    visto = _ler_ate(t, b"FIM")
    assert visto.endswith(b"FIM")
    assert t.inicio > 0
    _, dados, _ = t.ler(0, espera_s=0)
    assert len(dados) <= 1024  # quem pede do começo recebe só o que sobrou


def test_encerrar_para_o_programa(tmp_path: Path) -> None:
    t = Terminal(["sleep", "30"], tmp_path, {})
    t.encerrar()
    assert not t.vivo


@pytest.mark.parametrize("herda_saida", [True, False])
def test_encerrar_para_tambem_o_subprocesso_que_ignora_sinais(
    tmp_path: Path, herda_saida: bool
) -> None:
    filho = (
        "import os, signal, time; from pathlib import Path; "
        "signal.signal(signal.SIGHUP, signal.SIG_IGN); "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "Path('filho.pid').write_text(str(os.getpid())); "
        "print('filho pronto', flush=True); time.sleep(30)"
    )
    redirecionar = "" if herda_saida else ", stdout=subprocess.DEVNULL"
    programa = (
        "import subprocess, sys, time; from pathlib import Path; "
        f"subprocess.Popen([sys.executable, '-c', {filho!r}]{redirecionar}); "
        "\nwhile not Path('filho.pid').exists(): time.sleep(0.01)"
        "\nprint('filho pronto', flush=True); time.sleep(30)"
    )
    t = Terminal([sys.executable, "-c", programa], tmp_path, {})
    try:
        assert b"filho pronto" in _ler_ate(t, b"filho pronto")
        pid = int((tmp_path / "filho.pid").read_text())
        t.encerrar(espera_s=0.2)
        assert not t.vivo and not t.leitor.is_alive()
        estado = Path(f"/proc/{pid}/status")
        with contextlib.suppress(FileNotFoundError, ProcessLookupError):
            assert "State:\tZ" in estado.read_text()  # terminou; aguarda coleta pelo sistema
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(t.pid, signal.SIGKILL)
        t.encerrar(espera_s=1)


def test_encerrar_espera_o_callback_de_saida(tmp_path: Path) -> None:
    callback_iniciado = threading.Event()
    liberar = threading.Event()
    encerrado = threading.Event()

    def ao_sair(codigo: int) -> None:
        callback_iniciado.set()
        assert liberar.wait(5)

    t = Terminal(["sleep", "30"], tmp_path, {}, ao_sair)

    def encerrar() -> None:
        t.encerrar()
        encerrado.set()

    thread = threading.Thread(target=encerrar)
    thread.start()
    try:
        assert callback_iniciado.wait(5)
        assert not encerrado.wait(0.05)
    finally:
        liberar.set()
        thread.join(5)
    assert encerrado.is_set() and not t.leitor.is_alive()


def test_programa_inexistente_falha_antes_do_fork(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Terminal(["ze-nao-existe-123"], tmp_path, {})


def test_rascunho_espera_o_programa_abrir_e_nao_confirma(tmp_path: Path) -> None:
    t = Terminal(["sh", "-c", "sleep 0.3; printf pronto; read x; echo fim:$x"], tmp_path, {})
    t.rascunho("passagem ", quieto_s=0.2, minimo_s=0.5)
    time.sleep(1.5)
    t.escrever(b"pedido\r")
    assert b"fim:" in _ler_ate(t, b"fim:")
    t.encerrar()
