"""O supervisor das sessões (ADR 0068): reiniciar o Zé não derruba os agentes.

O aceite da Frente 1 do plano de maturidade: com três sessões trabalhando, o Zé reinicia e as
três continuam vivas, de volta à lista em menos de 10 s. Aqui o "Zé" que cai é um processo de
verdade, morto com SIGKILL (sem chance de arrumar nada), e o supervisor um processo à parte.
"""

import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from zervis.oficina import sessoes as modulo_sessoes
from zervis.oficina.sessoes import Sessoes
from zervis.oficina.supervisor import (
    PROTOCOLO,
    Oficina,
    Supervisor,
    SupervisorErro,
    TerminalRemoto,
)

pytestmark = pytest.mark.filterwarnings(
    "ignore:This process .* is multi-threaded:DeprecationWarning"
)
ECO = ["sh", "-c", 'printf "pronto\\n"; while read x; do echo "eco:$x"; done']


def _lancar(caminho: Path) -> None:
    """Como o `systemd-run` faz na máquina: um processo à parte, noutra sessão."""
    subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "zervis.oficina.supervisor", str(caminho)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


@pytest.fixture
def caminho() -> Iterator[Path]:
    # Curto: o endereço de um socket Unix tem no máximo 108 bytes.
    pasta = Path(tempfile.mkdtemp(prefix="ze-of-"))
    sock = pasta / "oficina.sock"
    yield sock
    oficina = Oficina(sock, lancar=None)
    if oficina.conectar():
        for info in oficina.listar():
            with contextlib.suppress(OSError, TimeoutError):
                oficina.encerrar(str(info["nome"]))
        with contextlib.suppress(OSError):
            oficina.pedir("sair")
    oficina.soltar()
    shutil.rmtree(pasta, ignore_errors=True)


def _ler_ate(t: TerminalRemoto, trecho: bytes, limite_s: float = 5.0) -> bytes:
    pos, visto = 0, b""
    prazo = time.monotonic() + limite_s
    while trecho not in visto and time.monotonic() < prazo:
        pos, dados, vivo = t.ler(pos, espera_s=0.2)
        visto += dados
        if not vivo:
            break
    return visto


def _esperar(condicao: Any, limite_s: float = 5.0) -> None:
    prazo = time.monotonic() + limite_s
    while not condicao():
        if time.monotonic() > prazo:
            raise AssertionError("demorou demais")
        time.sleep(0.02)


def test_abre_le_escreve_e_avisa_a_saida(tmp_path: Path, caminho: Path) -> None:
    oficina = Oficina(caminho, lancar=_lancar)
    assert oficina.conectar()
    saiu = threading.Event()
    codigos: list[int] = []
    lido: list[bytes] = []

    def ao_sair(codigo: int) -> None:
        codigos.append(codigo)
        saiu.set()

    t = oficina.abrir(
        "a1b2c3d4",
        ["sh", "-c", 'printf "pronto\\n"; read x; echo "eco:$x"; exit 3'],
        tmp_path,
        {},
        ao_sair,
        lido.append,
    )
    assert b"pronto" in _ler_ate(t, b"pronto")
    t.escrever(b"caju\r")
    assert b"eco:caju" in _ler_ate(t, b"eco:caju")
    assert saiu.wait(5) and codigos == [3] and not t.vivo
    assert b"eco:caju" in b"".join(lido)
    _esperar(lambda: oficina.listar() == [])  # tratado: o supervisor esquece o terminal
    oficina.soltar()


def test_o_ambiente_e_o_do_ze_e_nao_o_do_supervisor(tmp_path: Path, caminho: Path) -> None:
    """O Zé aplica a conta do Claude no próprio ambiente; o supervisor subiu antes, com outro."""
    oficina = Oficina(caminho, lancar=_lancar)
    assert oficina.conectar()
    t = oficina.abrir(
        "a1b2c3d5", ["sh", "-c", 'echo "conta:$ZE_CONTA_TESTE"'], tmp_path, {"ZE_CONTA_TESTE": "b"}
    )
    assert b"conta:b" in _ler_ate(t, b"conta:b")
    oficina.soltar()


def test_agente_nao_instalado_e_terminal_ocupado(tmp_path: Path, caminho: Path) -> None:
    oficina = Oficina(caminho, lancar=_lancar)
    assert oficina.conectar()
    with pytest.raises(FileNotFoundError):
        oficina.abrir("a1b2c3d6", ["ze-nao-existe-123"], tmp_path, {})
    t = oficina.abrir("a1b2c3d6", ["sleep", "30"], tmp_path, {})
    with pytest.raises(SupervisorErro, match="já está aberto"):
        oficina.abrir("a1b2c3d6", ["sleep", "30"], tmp_path, {})
    t.encerrar()
    assert not t.vivo
    oficina.soltar()


ZE_QUE_CAI = textwrap.dedent(
    """
    import sys, time
    from pathlib import Path
    from zervis.oficina.supervisor import Oficina
    oficina = Oficina(Path(sys.argv[1]), lancar=None)
    assert oficina.conectar()
    for nome in ("00000001", "00000002", "00000003"):
        oficina.abrir(nome, {eco!r}, Path(sys.argv[2]), {{}})
    print("abertos", flush=True)
    time.sleep(60)
    """
)


def test_reiniciar_o_ze_mantem_as_tres_sessoes_vivas(tmp_path: Path, caminho: Path) -> None:
    """O aceite da Frente 1: o Zé cai com três terminais abertos e volta a vê-los, vivos e
    respondendo, em menos de 10 s."""
    assert Oficina(caminho, lancar=_lancar).conectar()
    ze = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", ZE_QUE_CAI.format(eco=ECO), str(caminho), str(tmp_path)],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert ze.stdout is not None and ze.stdout.readline().strip() == "abertos"
    time.sleep(0.3)  # os três escreveram o "pronto"
    os.kill(ze.pid, signal.SIGKILL)
    ze.wait(5)
    caiu = time.monotonic()

    oficina = Oficina(caminho, lancar=_lancar)
    assert oficina.conectar()
    achados = {str(i["nome"]): i for i in oficina.listar()}
    assert sorted(achados) == ["00000001", "00000002", "00000003"]
    assert all(i["vivo"] for i in achados.values())
    lido: list[bytes] = []
    terminais = [oficina.retomar(i, ao_ler=lido.append) for i in achados.values()]
    for t in terminais:
        t.escrever(b"continua\r")
    for t in terminais:
        visto = _ler_ate(t, b"eco:continua")
        assert b"pronto" in visto  # a tela reaberta mostra o que já tinha passado
        assert b"eco:continua" in visto
    assert time.monotonic() - caiu < 10
    # O que saiu antes do reinício não volta para quem confere a saída (limite de conta).
    assert b"pronto" not in b"".join(lido)
    oficina.soltar()


def _agente_falso(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo_sessoes, "comando_terminal", lambda *a, **k: list(ECO))
    monkeypatch.setattr(modulo_sessoes, "confiar_pasta_claude", lambda s: None)
    monkeypatch.setattr(modulo_sessoes, "conversa_claude_existe", lambda s: False)


def test_sessoes_trabalhando_continuam_depois_do_reinicio(
    tmp_path: Path, caminho: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """As sessões não viram "interrompidas" e o turno que terminou durante o reinício é
    contado uma vez, com a resposta, pelo evento que o agente escreveu enquanto o Zé caía."""
    _agente_falso(monkeypatch)
    projeto = tmp_path / "casa" / "loja"
    projeto.mkdir(parents=True)
    antes = Sessoes(
        tmp_path / "sessoes", (tmp_path / "casa",), oficina=Oficina(caminho, lancar=_lancar)
    )
    assert antes.oficina is not None
    ids = [antes.criar(f"Loja {n}", str(projeto), "claude").id for n in range(3)]
    for id_ in ids:
        antes.enviar(id_, "rode os testes")
    assert all(isinstance(antes.terminais[i], TerminalRemoto) for i in ids)
    assert sorted(antes.trabalhando()) == sorted(ids)
    pid = antes.terminais[ids[0]].pid
    antes.soltar_terminais()  # o Zé caiu
    # Enquanto ele estava fora, o agente da primeira terminou o turno.
    fim = {"hook_event_name": "Stop", "last_assistant_message": "Testes verdes.", "prompt_id": ""}
    with antes.eventos(ids[0]).open("a") as f:
        f.write(json.dumps(fim) + "\n")

    avisos: list[tuple[str, str]] = []
    depois = Sessoes(
        tmp_path / "sessoes",
        (tmp_path / "casa",),
        lambda s, resumo: avisos.append((s.id, resumo)),
        oficina=Oficina(caminho, lancar=_lancar),
    )
    assert depois.interrompidas_ao_subir == []
    assert sorted(depois.terminais) == sorted(ids)
    assert all(depois.terminais[i].vivo for i in ids)
    assert depois.terminais[ids[0]].pid == pid  # o mesmo agente: o painel não reinicia a tela
    _esperar(lambda: avisos)
    assert avisos == [(ids[0], "Testes verdes.")]
    assert depois.ler(ids[0]).estado == "parada"
    assert [depois.ler(i).estado for i in ids[1:]] == ["trabalhando", "trabalhando"]
    # E o agente continua recebendo pedidos.
    depois.enviar(ids[1], "e agora o lint")
    remoto = depois.terminais[ids[1]]
    assert isinstance(remoto, TerminalRemoto)
    assert b"e agora o lint" in _ler_ate(remoto, b"e agora o lint\x1b[201~\r\n")
    depois.soltar_terminais()


def test_chave_de_permissao_continua_valendo(
    tmp_path: Path, caminho: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O gancho de permissão do agente leva a chave de quando o terminal abriu: o Zé novo a
    reconhece pelo resumo guardado no supervisor."""
    _agente_falso(monkeypatch)
    projeto = tmp_path / "casa" / "loja"
    projeto.mkdir(parents=True)
    antes = Sessoes(
        tmp_path / "sessoes", (tmp_path / "casa",), oficina=Oficina(caminho, lancar=_lancar)
    )
    antes.permissoes.endereco = "http://127.0.0.1:1/permissao"
    chaves: list[str] = []
    original = antes.permissoes.chave

    def guardar_chave(sessao: str, prazo_s: float | None = None) -> str:
        chaves.append(original(sessao, prazo_s))
        return chaves[-1]

    monkeypatch.setattr(antes.permissoes, "chave", guardar_chave)
    s = antes.criar("Loja", str(projeto), "claude")
    antes.abrir_terminal(s.id)
    antes.soltar_terminais()

    depois = Sessoes(
        tmp_path / "sessoes", (tmp_path / "casa",), oficina=Oficina(caminho, lancar=_lancar)
    )
    assert chaves and depois.permissoes.sessao_da_chave(chaves[0]) == s.id
    depois.terminais[s.id].encerrar()
    _esperar(lambda: depois.permissoes.sessao_da_chave(chaves[0]) is None)
    depois.soltar_terminais()


def test_supervisor_de_protocolo_antigo_sem_terminais_e_trocado(caminho: Path) -> None:
    antigo = Supervisor(caminho)
    antigo.preparar()
    original = antigo._op_ola

    def ola_antigo(p: dict[str, Any]) -> dict[str, Any]:
        return {**original(p), "protocolo": PROTOCOLO - 1}

    antigo._op_ola = ola_antigo  # type: ignore[method-assign,assignment]
    fio = threading.Thread(target=antigo.servir, daemon=True)
    fio.start()
    lancados: list[Path] = []

    def lancar(c: Path) -> None:
        fio.join(5)  # o antigo saiu e soltou a trava
        lancados.append(c)
        _lancar(c)

    assert Oficina(caminho, lancar=lancar).conectar()
    assert lancados == [caminho] and not fio.is_alive()


def test_sem_supervisor_os_terminais_ficam_no_ze(tmp_path: Path) -> None:
    """Falhar fechado é seguir funcionando: sem o supervisor, a sessão abre como antes."""

    def nao_sobe(c: Path) -> None:
        raise OSError("sem systemd-run")

    sessoes = Sessoes(
        tmp_path / "sessoes", (tmp_path,), oficina=Oficina(tmp_path / "x.sock", lancar=nao_sobe)
    )
    assert sessoes.oficina is None


def test_socket_so_do_usuario(caminho: Path) -> None:
    assert Oficina(caminho, lancar=_lancar).conectar()
    assert (caminho.stat().st_mode & 0o777) == 0o600
