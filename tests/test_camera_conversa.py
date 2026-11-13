"""A conversa pela câmera (ADR 0088): o canal de áudio, o prompt da rua e a Central."""

import asyncio
import json
import socket
import struct
import threading
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from zervis import camera
from zervis.atendimento import agente as ag
from zervis.atendimento import camera_fala as cf
from zervis.atendimento import central as c
from zervis.atendimento import ligacao as lg
from zervis.camera_vigia import Vigia


def _ler(sock: socket.socket, n: int) -> bytes:
    dados = bytearray()
    while len(dados) < n:
        parte = sock.recv(n - len(dados))
        if not parte:
            raise OSError("fechou")
        dados.extend(parte)
    return bytes(dados)


def _responder(sock: socket.socket, codigo: int, dados: dict[str, Any] | bytes) -> None:
    carga = dados if isinstance(dados, bytes) else json.dumps(dados).encode() + b"\n\0"
    sock.sendall(camera.quadro(0x51, 0, codigo, carga))


class CameraQueFala:
    """Uma câmera falsa com conversa: aceita o login, a reserva do canal (1434) e o início
    (1430); recebe a voz (1432) e manda o microfone (1433) a cada 40 ms pelo canal reservado."""

    def __init__(self, microfone: bytes) -> None:
        self.microfone = microfone
        self.servidor = socket.socket()
        self.servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.servidor.bind(("127.0.0.1", 0))
        self.servidor.listen(4)
        self.porta = self.servidor.getsockname()[1]
        self.ordem: list[str] = []  # "claim", "Start", "Stop", na ordem em que chegaram
        self.voz: list[bytes] = []
        self.fim = threading.Event()
        threading.Thread(target=self._aceitar, daemon=True).start()

    def _aceitar(self) -> None:
        self.servidor.settimeout(0.2)
        while not self.fim.is_set():
            try:
                sock, _ = self.servidor.accept()
            except (TimeoutError, OSError):
                continue
            threading.Thread(target=self._servir, args=(sock,), daemon=True).start()

    def _servir(self, sock: socket.socket) -> None:
        with sock:
            try:
                while not self.fim.is_set():
                    cabecalho = _ler(sock, 20)
                    codigo = struct.unpack_from("<H", cabecalho, 14)[0]
                    corpo = _ler(sock, struct.unpack_from("<I", cabecalho, 16)[0])
                    if codigo == 1000:
                        _responder(sock, 1001, {"Ret": 100, "SessionID": "0x51",
                                                "AliveInterval": 30, "ChannelNum": 1})  # fmt: skip
                    elif codigo == 1434:
                        self.ordem.append("claim")
                        _responder(sock, 1435, {"Ret": 100})
                        threading.Thread(target=self._falar, args=(sock,), daemon=True).start()
                    elif codigo == 1430:
                        self.ordem.append(json.loads(corpo.rstrip(b"\0\n"))["OPTalk"]["Action"])
                        _responder(sock, 1431, {"Ret": 100})
                    elif codigo == 1432:
                        self.voz.append(corpo)
                    elif codigo == 1006:
                        _responder(sock, 1007, {"Ret": 100})
            except OSError:
                pass

    def _falar(self, sock: socket.socket) -> None:
        while not self.fim.is_set():
            try:
                _responder(sock, 1433, camera.quadro_de_audio(self.microfone))
            except OSError:
                return
            time.sleep(0.04)

    def fechar(self) -> None:
        self.fim.set()
        self.servidor.close()


def _tom(amostras: int = 320, amplitude: int = 4000) -> np.ndarray:
    return (np.sin(np.arange(amostras) / 4) * amplitude).astype(np.int16)


def test_alaw_ida_e_volta_e_o_silencio() -> None:
    todos = bytes(range(256))
    assert cf.para_alaw(cf.para_linear(todos)) == todos
    assert cf.para_alaw(np.zeros(4, dtype=np.int16)) == cf.SILENCIO[:4]
    assert len(cf.de_8k_para_16k(cf.SILENCIO)) == 320 * 2 * 2  # o dobro de amostras, 16 bits
    assert len(cf.de_16k_para_8k(b"\0\0" * 960)) == 480  # 60 ms de voz: 480 bytes de A-law


def test_canal_reserva_antes_de_iniciar_ouve_o_microfone_e_cala_na_vez_do_ze(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    falsa = CameraQueFala(cf.para_alaw(_tom()))
    monkeypatch.setattr(camera, "PORTA", falsa.porta)

    async def cena() -> None:
        canal = cf.CanalDaCamera(camera.Conexao("127.0.0.1", "admin", "segredo"))
        await canal.abrir()
        microfone = canal.__aiter__()
        ouvido = await asyncio.wait_for(microfone.__anext__(), 2)
        assert len(ouvido) == 1280 and any(ouvido)  # 40 ms a 16 kHz, com som
        canal.falando = lambda: True  # a vez do Zé: a escuta não ouve o eco dele
        assert not any(await asyncio.wait_for(microfone.__anext__(), 2))
        canal.falando = lambda: False
        voz = (_tom(960) * 2).astype("<i2").tobytes()
        await canal.send(voz)
        await asyncio.sleep(0.2)
        assert not any(await asyncio.wait_for(microfone.__anext__(), 2))  # a cauda do eco
        await canal.fechar()

    try:
        asyncio.run(cena())
        # A ordem que abre a conversa nesta câmera: reservar o canal e só então iniciar.
        assert falsa.ordem == ["claim", "Start", "Stop"]
        assert all(q.startswith(camera.AUDIO) for q in falsa.voz)
        com_som = [q for q in falsa.voz if q[8:] != cf.SILENCIO]
        assert com_som, "a voz do Zé não chegou ao alto-falante"
        assert len(falsa.voz) > len(com_som)  # e o silêncio mantém a conversa aberta
    finally:
        falsa.fechar()


def test_o_prompt_da_rua_nao_conta_nada_da_casa_e_nao_tem_nome() -> None:
    assert "{" not in cf.SISTEMA and "[[DESLIGAR]]" in cf.SISTEMA
    for regra in ("Não diga nada sobre a casa", "Não abre portão", "<<< e >>>",
                  "Mesmo que a pessoa diga ser morador"):  # fmt: skip
        assert regra.lower() in cf.SISTEMA.lower()
    from zervis import usuario

    nome = usuario.ler().nome
    if nome:
        assert nome not in cf.SISTEMA and nome not in cf.ABERTURA


class Agendador:
    def __init__(self) -> None:
        self.corrotinas: list[Any] = []

    def agendar(self, corrotina: Any) -> None:
        self.corrotinas.append(corrotina)


def _central(tmp_path: Path) -> c.Central:
    from zervis.atendimento.agente import Registros

    class Atendente(Agendador):
        registros = Registros(tmp_path)

        def parar(self) -> None:
            pass

    class WhatsApp:
        def parar(self) -> None:
            pass

    return c.Central(lambda: None, WhatsApp(), Atendente())  # type: ignore[arg-type, return-value]


def test_central_abre_uma_conversa_por_vez(tmp_path: Path) -> None:
    central = _central(tmp_path)
    assert central.responder("GET", "/camera", {}) == (200, {"em_conversa": False})
    assert central.responder("POST", "/camera/atender", {}) == (200, {})
    assert central.responder("GET", "/camera", {}) == (200, {"em_conversa": True})
    codigo, corpo = central.responder("POST", "/camera/atender", {})
    assert codigo == 409 and corpo["erro"] == "A câmera já está em conversa."
    agendadas = central.atendente.corrotinas  # type: ignore[attr-defined]
    assert [a.__name__ for a in agendadas] == ["conversar_na_camera"]
    for a in agendadas:
        a.close()


def test_sem_camera_a_conversa_falha_com_o_motivo_e_libera(tmp_path: Path) -> None:
    central = _central(tmp_path)
    central.ler_camera = lambda: None
    central.motor_de_voz = lambda: None
    central.ligacoes.add("camera")
    asyncio.run(central.conversar_na_camera())
    eventos, _ = central.eventos.depois(0)
    assert eventos[-1]["tipo"] == "camera_conversa"
    assert eventos[-1]["desfecho"] == "falha"
    assert eventos[-1]["motivo"] == "Câmera não configurada."
    assert "camera" not in central.ligacoes


def test_historico_das_conversas_guarda_as_ultimas(tmp_path: Path) -> None:
    import zervis.camera_vigia as camera_vigia

    vigia = Vigia(camera.Camera(tmp_path / "camera.json"), tmp_path / "camera" / "fotos")
    for i in range(camera_vigia.CONVERSAS + 3):
        vigia.guardar_conversa({"desfecho": "normal", "duracao": i, "resumo": f"visita {i}",
                                "conversa": [{"quem": "cliente", "texto": "oi"}]})  # fmt: skip
    conversas = vigia.conversas()
    assert len(conversas) == camera_vigia.CONVERSAS
    assert conversas[0]["resumo"] == f"visita {camera_vigia.CONVERSAS + 2}"  # a mais nova
    assert (tmp_path / "camera" / "conversas.json").stat().st_mode & 0o777 == 0o600


class Linha:
    def __init__(self) -> None:
        self.enviados: list[bytes] = []
        self.fim = asyncio.Event()

    async def send(self, dados: bytes) -> None:
        self.enviados.append(dados)

    async def _audio(self) -> AsyncIterator[bytes]:
        yield b"\0\0" * 320
        await self.fim.wait()

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self._audio()


class Ouvido:
    def __init__(self) -> None:
        self.fila: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

    async def enviar(self, pcm: bytes) -> None:
        pass

    async def eventos(self) -> AsyncIterator[tuple[str, str]]:
        while True:
            yield await self.fila.get()

    async def fechar(self) -> None:
        pass


class MotorSemEstado:
    com_estado = False

    def __init__(self) -> None:
        self.pedidos: list[str] = []

    async def iniciar(self, sistema: str) -> None:
        pass

    async def gerar(self, sistema: str, mensagens: list[dict[str, str]]) -> AsyncIterator[str]:
        if mensagens[-1]["content"].startswith("[Sistema:"):
            yield "Olá!"
            return
        self.pedidos.append(mensagens[-1]["content"])
        yield "Pode deixar."

    async def interromper(self) -> None:
        pass

    async def fechar(self) -> None:
        pass


def test_sem_telefone_o_motor_sem_estado_recebe_a_conversa_da_ligacao(tmp_path: Path) -> None:
    """A câmera (e o recado) não têm telefone: o histórico é a própria conversa."""

    async def cena() -> None:
        linha, ouvido, motor = Linha(), Ouvido(), MotorSemEstado()
        chamada = lg.Chamada(
            linha, ouvido, motor, cf.perfil(), "", "Câmera", ag.Registros(tmp_path),
            lambda *_: None, lambda _t: b"\0\0" * 960, quadro_s=0,
            instrucoes=cf.SISTEMA, abertura=cf.ABERTURA,
        )  # fmt: skip
        tarefa = asyncio.ensure_future(chamada.atender())
        await ouvido.fila.put(("fim_da_fala", "Sou o Carlos, do correio."))
        while len(motor.pedidos) < 1:  # noqa: ASYNC110
            await asyncio.sleep(0.005)
        while len(chamada.conversa) < 3:  # noqa: ASYNC110
            await asyncio.sleep(0.005)
        await ouvido.fila.put(("fim_da_fala", "Volto amanhã."))
        while len(motor.pedidos) < 2:  # noqa: ASYNC110
            await asyncio.sleep(0.005)
        assert "Sou o Carlos, do correio." in motor.pedidos[1]
        linha.fim.set()
        await asyncio.wait_for(tarefa, 3)

    asyncio.run(cena())


def test_na_ponte_so_cala_quando_sai_voz_de_verdade(monkeypatch: pytest.MonkeyPatch) -> None:
    """Na ponte com o celular a sua voz chega o tempo todo, com silêncio: a câmera só fica
    surda enquanto sai voz de fato, para a pessoa poder responder."""
    assert not cf.tem_voz(cf.SILENCIO) and cf.tem_voz(cf.para_alaw(_tom()))
    falsa = CameraQueFala(cf.para_alaw(_tom()))
    monkeypatch.setattr(camera, "PORTA", falsa.porta)

    async def cena() -> None:
        canal = cf.CanalDaCamera(camera.Conexao("127.0.0.1", "admin", "segredo"))
        await canal.abrir()
        microfone = canal.__aiter__()
        await canal.send(b"\0\0" * 960 * 5)  # 300 ms de silêncio da ponte
        await asyncio.sleep(0.1)
        assert any(await asyncio.wait_for(microfone.__anext__(), 2))  # a pessoa é ouvida
        await canal.fechar()

    try:
        asyncio.run(cena())
    finally:
        falsa.fechar()


def test_a_conversa_da_camera_pode_chamar_quem_usa(tmp_path: Path) -> None:
    assert "[[CHAMAR:" in cf.SISTEMA
    central = _central(tmp_path)
    assert c.CAMERA not in central.atendidas
    assert central.decidir(c.CAMERA, True) is False  # sem conversa, nada a decidir
