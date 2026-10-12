"""O terminal das sessões: um programa real num PTY, lido a partir de uma posição."""

import threading
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


def test_programa_inexistente_falha_antes_do_fork(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Terminal(["ze-nao-existe-123"], tmp_path, {})
