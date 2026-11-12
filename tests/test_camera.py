"""Câmera iCSee: protocolo local, segredos e fotos de movimento."""

import json
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from zervis import camera
from zervis.camera_vigia import Vigia

JPEG = b"\xff\xd8foto\xff\xd9"


def _ler(sock: socket.socket, tamanho: int) -> bytes:
    dados = bytearray()
    while len(dados) < tamanho:
        parte = sock.recv(tamanho - len(dados))
        if not parte:
            raise OSError("conexão fechada")
        dados.extend(parte)
    return bytes(dados)


class DVRFalso:
    def __init__(
        self, ret: int = 100, derrubar_primeira_sessao: bool = False, lentes: int = 1
    ) -> None:
        self.ret = ret
        self.lentes = lentes
        # Como vem de fábrica: detecta, mas não manda o alarme aos clientes da rede.
        self.deteccao: list[dict[str, Any]] = [
            {"Enable": True, "Level": 3, "EventHandler": {"MsgtoNetEnable": False}}
            for _ in range(lentes)
        ]
        self.gravacoes = 0
        self.fotos_pedidas: list[int] = []
        self.derrubar_primeira_sessao = derrubar_primeira_sessao
        self.servidor = socket.socket()
        self.servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.servidor.bind(("127.0.0.1", 0))
        self.servidor.listen(1)
        self.porta = self.servidor.getsockname()[1]
        self.terminar = threading.Event()
        self.pronto = threading.Event()
        self._trava = threading.Lock()
        self._ativo: socket.socket | None = None
        self.logins = 0
        self.pedido_login: dict[str, Any] = {}
        self.comandos: list[int] = []
        self.thread = threading.Thread(target=self._servir, daemon=True)
        self.thread.start()

    def _responder(self, sock: socket.socket, comando: int, dados: bytes) -> None:
        cabecalho = struct.pack("<BBHIIBBHI", 0xFF, 0, 0, 0x51, 1, 1, 0, comando, len(dados))
        sock.sendall(cabecalho + dados)

    def _servir(self) -> None:
        try:
            self.servidor.settimeout(0.5)
            while not self.terminar.is_set():
                try:
                    sock, _ = self.servidor.accept()
                except TimeoutError:
                    continue
                with self._trava:
                    self._ativo = sock
                with sock:
                    sock.settimeout(30)
                    while not self.terminar.is_set():
                        try:
                            cabecalho = _ler(sock, 20)
                        except (TimeoutError, OSError):
                            break
                        comando = struct.unpack_from("<H", cabecalho, 14)[0]
                        tamanho = struct.unpack_from("<I", cabecalho, 16)[0]
                        corpo = _ler(sock, tamanho)
                        dados = json.loads(corpo.rstrip(b"\0\n")) if corpo.endswith(b"\0") else {}
                        self.comandos.append(comando)
                        if comando == 1000:
                            self.logins += 1
                            self.pedido_login = dados
                            resposta = {
                                "Ret": self.ret,
                                "SessionID": "0x00000051",
                                "AliveInterval": 21,
                                "ChannelNum": self.lentes,
                            }
                            self._responder(sock, 1001, json.dumps(resposta).encode() + b"\n\0")
                            if self.ret not in (100, 515):
                                break
                        elif comando == 1560:
                            self.fotos_pedidas.append(int(dados["OPSNAP"]["Channel"]))
                            self._responder(sock, 1561, JPEG)
                        elif comando == 1042:
                            nome = dados["Name"]
                            corpo_ = {"Name": nome, "Ret": 100, nome: self.deteccao}
                            self._responder(sock, 1043, json.dumps(corpo_).encode() + b"\n\0")
                        elif comando == 1040:
                            self.gravacoes += 1
                            self.deteccao = dados[dados["Name"]]
                            self._responder(sock, 1041, b'{"Ret":100}\n\0')
                        elif comando == 1500:
                            self._responder(sock, 1501, b'{"Ret":100}\n\0')
                            self.pronto.set()
                            if self.derrubar_primeira_sessao and self.logins == 1:
                                break
                        elif comando == 1006:
                            self._responder(sock, 1007, b'{"Ret":100}\n\0')
                with self._trava:
                    if self._ativo is sock:
                        self._ativo = None
        except (OSError, TimeoutError):
            pass

    def alarme(self, evento: str, status: str, canal: int = 0) -> None:
        with self._trava:
            sock = self._ativo
            if sock is None:
                raise RuntimeError("sem cliente conectado")
            self._responder(
                sock,
                1504,
                json.dumps(
                    {
                        "Name": "AlarmInfo",
                        "AlarmInfo": {"Event": evento, "Status": status, "Channel": canal},
                    }
                ).encode()
                + b"\n\0",
            )

    def fechar(self) -> None:
        self.terminar.set()
        with self._trava:
            ativo = self._ativo
            self._ativo = None
        if ativo is not None:
            ativo.close()
        self.servidor.close()
        self.thread.join(timeout=1)


def test_cliente_sofia_faz_login_e_recebe_foto(monkeypatch: pytest.MonkeyPatch) -> None:
    dvr = DVRFalso()
    monkeypatch.setattr(camera, "PORTA", dvr.porta)
    conexao = camera.Conexao("127.0.0.1", "admin", "segredo")
    try:
        with camera.Cliente(conexao) as cliente:
            assert cliente.foto() == JPEG
        assert dvr.pedido_login["PassWord"] == camera.hash_sofia("segredo")
        assert dvr.pedido_login["UserName"] == "admin"
        assert 1560 in dvr.comandos
    finally:
        dvr.fechar()


def test_vigia_guarda_foto_ao_receber_alarme_sofia(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dvr = DVRFalso()
    monkeypatch.setattr(camera, "PORTA", dvr.porta)
    dispositivo = camera.Camera(tmp_path / "camera.json")
    dispositivo.guardar("127.0.0.1", "admin", "segredo")
    vigia = Vigia(dispositivo, tmp_path / "fotos")
    try:
        vigia.iniciar()
        assert dvr.pronto.wait(2)
        dvr.alarme("MotionDetect", "Start")
        limite = time.monotonic() + 2
        while not list((tmp_path / "fotos").glob("*.jpg")) and time.monotonic() < limite:
            time.sleep(0.01)
        fotos = list((tmp_path / "fotos").glob("*.jpg"))
        assert len(fotos) == 1
        assert fotos[0].read_bytes() == JPEG
        assert dvr.logins == 1  # usa a sessão contínua, sem abrir outro login
    finally:
        vigia.parar()
        dvr.fechar()


def test_vigia_reconecta_depois_da_queda(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import zervis.camera_vigia as camera_vigia

    dvr = DVRFalso(derrubar_primeira_sessao=True)
    monkeypatch.setattr(camera, "PORTA", dvr.porta)
    monkeypatch.setattr(camera_vigia, "ESPERA_RECONEXAO", 0.01)
    dispositivo = camera.Camera(tmp_path / "camera.json")
    dispositivo.guardar("127.0.0.1", "admin", "segredo")
    vigia = Vigia(dispositivo, tmp_path / "fotos")
    try:
        vigia.iniciar()
        limite = time.monotonic() + 2
        while dvr.logins < 2 and time.monotonic() < limite:
            time.sleep(0.01)
        assert dvr.logins >= 2
        assert vigia.estado() == "Conectada"
    finally:
        vigia.parar()
        dvr.fechar()


def test_login_recusado_nao_tenta_outra_senha(monkeypatch: pytest.MonkeyPatch) -> None:
    dvr = DVRFalso(ret=205)
    monkeypatch.setattr(camera, "PORTA", dvr.porta)
    try:
        with (
            pytest.raises(camera.CredenciaisInvalidas, match="Usuário ou senha inválidos"),
            camera.Cliente(camera.Conexao("127.0.0.1", "admin", "senha")),
        ):
            pass
        assert dvr.comandos == [1000]
    finally:
        dvr.fechar()


def test_config_salva_senha_local_sem_devolve_la_para_tela(tmp_path: Path) -> None:
    dispositivo = camera.Camera(tmp_path / "config" / "camera.json")
    dispositivo.guardar("127.0.0.1", "admin", "segredo", 30, True)
    estado = dispositivo.para_tela()
    assert estado == {
        "configurada": True,
        "ip": "127.0.0.1",
        "usuario": "admin",
        "intervalo_s": 30,
        "ligado": True,
        "girar": [],
        "enviar": True,
    }
    assert "senha" not in estado
    assert (tmp_path / "config" / "camera.json").stat().st_mode & 0o777 == 0o600


def test_movimento_start_guarda_uma_foto_e_stop_nao_guarda(tmp_path: Path) -> None:
    dispositivo = camera.Camera(tmp_path / "camera.json")
    dispositivo.guardar("127.0.0.1", "admin", "segredo")
    dispositivo.foto = lambda canal=0: JPEG  # type: ignore[method-assign]
    vigia = Vigia(dispositivo, tmp_path / "fotos")

    vigia._ao_alarme({"Event": "MotionDetect", "Status": "Stop"})
    vigia._ao_alarme({"Event": "MotionDetect", "Status": "Start"})
    vigia._ao_alarme({"Event": "MotionDetect", "Status": "Start"})
    limite = time.monotonic() + 2
    while not list((tmp_path / "fotos").glob("*.jpg")) and time.monotonic() < limite:
        time.sleep(0.01)

    fotos = list((tmp_path / "fotos").glob("*.jpg"))
    assert len(fotos) == 1
    assert fotos[0].read_bytes() == JPEG
    assert len(fotos[0].stem.split("-")[0]) == 8
    assert not hasattr(vigia, "avisar")  # nunca fala


def test_guarda_limite_de_fotos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import zervis.camera_vigia as camera_vigia

    monkeypatch.setattr(camera_vigia, "FOTOS", 2)
    dispositivo = camera.Camera(tmp_path / "camera.json")
    vigia = Vigia(dispositivo, tmp_path / "fotos")
    for _ in range(3):
        vigia.guardar_foto(JPEG)
    assert len(list((tmp_path / "fotos").glob("*.jpg"))) == 2


def _esperar_fotos(pasta: Path, quantas: int = 1) -> list[Path]:
    limite = time.monotonic() + 2
    while len(list(pasta.glob("*.jpg"))) < quantas and time.monotonic() < limite:
        time.sleep(0.01)
    return sorted(pasta.glob("*.jpg"))


def test_vigia_liga_o_alarme_na_rede_e_fotografa_a_lente_que_viu_a_pessoa(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dvr = DVRFalso(lentes=3)
    monkeypatch.setattr(camera, "PORTA", dvr.porta)
    dispositivo = camera.Camera(tmp_path / "camera.json")
    dispositivo.guardar("127.0.0.1", "admin", "segredo")
    vigia = Vigia(dispositivo, tmp_path / "fotos")
    try:
        vigia.iniciar()
        assert dvr.pronto.wait(2)
        assert [d["EventHandler"]["MsgtoNetEnable"] for d in dvr.deteccao] == [True] * 3
        assert dvr.deteccao[0]["Level"] == 3  # o resto da configuração fica como estava
        # O nome que o firmware iCSee manda para pessoa detectada; o Stop não fotografa.
        dvr.alarme("appEventHumanDetectAlarm", "Stop", canal=2)
        dvr.alarme("appEventHumanDetectAlarm", "Start", canal=2)
        dvr.alarme("VideoMotion", "Start", canal=1)
        fotos = _esperar_fotos(tmp_path / "fotos", 2)
        assert sorted(dvr.fotos_pedidas) == [1, 2]
        assert sorted(f.stem.split("-")[-1] for f in fotos) == ["lente2", "lente3"]
        assert {foto["lente"] for foto in vigia.fotos()} == {2, 3}
    finally:
        vigia.parar()
        dvr.fechar()


def test_alarme_ja_ligado_na_camera_nao_regrava_a_configuracao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dvr = DVRFalso()
    dvr.deteccao[0]["EventHandler"]["MsgtoNetEnable"] = True
    monkeypatch.setattr(camera, "PORTA", dvr.porta)
    try:
        with camera.Cliente(camera.Conexao("127.0.0.1", "admin", "segredo")) as cliente:
            assert cliente.ligar_alarmes_na_rede() is False
        assert dvr.gravacoes == 0
    finally:
        dvr.fechar()


def test_intervalo_entre_fotos_vale_por_lente(tmp_path: Path) -> None:
    dispositivo = camera.Camera(tmp_path / "camera.json")
    dispositivo.guardar("127.0.0.1", "admin", "segredo")
    pedidas: list[int] = []

    def foto(canal: int = 0) -> bytes:
        pedidas.append(canal)
        return JPEG

    dispositivo.foto = foto  # type: ignore[method-assign]
    vigia = Vigia(dispositivo, tmp_path / "fotos")
    vigia.lentes = 2
    vigia._ao_alarme({"Event": "appEventHumanDetectAlarm", "Status": "Start", "Channel": 0})
    vigia._ao_alarme({"Event": "appEventHumanDetectAlarm", "Status": "Start", "Channel": 0})
    vigia._ao_alarme({"Event": "appEventHumanDetectAlarm", "Status": "Start", "Channel": 1})
    vigia._ao_alarme({"Event": "VideoBlind", "Status": "Start", "Channel": 1})  # não é movimento
    assert len(_esperar_fotos(tmp_path / "fotos", 2)) == 2
    assert sorted(pedidas) == [0, 1]


def test_foto_agora_tira_uma_de_cada_lente(tmp_path: Path) -> None:
    dispositivo = camera.Camera(tmp_path / "camera.json")
    dispositivo.guardar("127.0.0.1", "admin", "segredo")
    dispositivo.foto = lambda canal=0: JPEG  # type: ignore[method-assign]
    vigia = Vigia(dispositivo, tmp_path / "fotos")
    vigia.lentes = 3
    assert [c.stem.split("-")[-1] for c in vigia.fotos_agora()] == ["lente1", "lente2", "lente3"]
    vigia.lentes = 1
    assert "lente" not in vigia.fotos_agora()[0].name


def _jpeg_meio_claro() -> bytes:
    """Metade de cima branca e a de baixo preta: o giro de 180° troca as duas."""
    from io import BytesIO

    from PIL import Image

    imagem = Image.new("L", (32, 32), 0)
    imagem.paste(255, (0, 0, 32, 16))
    saida = BytesIO()
    imagem.save(saida, "JPEG", quality=95)
    return saida.getvalue()


def _cima_claro(jpeg: bytes) -> bool:
    from io import BytesIO

    from PIL import Image

    with Image.open(BytesIO(jpeg)) as imagem:
        cinza = imagem.convert("L")
        return int(cinza.getpixel((16, 4)) or 0) > int(cinza.getpixel((16, 28)) or 0)


def test_lente_marcada_para_girar_sai_de_pe_e_as_outras_como_vieram(tmp_path: Path) -> None:
    dispositivo = camera.Camera(tmp_path / "camera.json")
    dispositivo.guardar("127.0.0.1", "admin", "segredo", girar=[2, 3])
    vigia = Vigia(dispositivo, tmp_path / "fotos")
    foto = _jpeg_meio_claro()
    assert not _cima_claro(vigia.guardar_foto(foto, 1).read_bytes())  # lente 2: girada
    assert _cima_claro(vigia.guardar_foto(foto, 0).read_bytes())  # lente 1: como veio
    assert dispositivo.para_tela()["girar"] == [2, 3]


def test_salvar_sem_lentes_mantem_o_giro_e_lista_vazia_desliga(tmp_path: Path) -> None:
    dispositivo = camera.Camera(tmp_path / "camera.json")
    dispositivo.guardar("127.0.0.1", "admin", "segredo", girar=[1])
    dispositivo.guardar("127.0.0.1", "admin", "")
    assert dispositivo.conexao() is not None
    assert dispositivo.conexao().girar == (1,)  # type: ignore[union-attr]
    dispositivo.guardar("127.0.0.1", "admin", "", girar=[])
    assert dispositivo.conexao().girar == ()  # type: ignore[union-attr]
    vigia = Vigia(dispositivo, tmp_path / "fotos")
    assert _cima_claro(vigia.guardar_foto(_jpeg_meio_claro()).read_bytes())


def test_foto_de_movimento_vai_ao_celular_e_a_tirada_na_hora_nao(tmp_path: Path) -> None:
    dispositivo = camera.Camera(tmp_path / "camera.json")
    dispositivo.guardar("127.0.0.1", "admin", "segredo")
    dispositivo.foto = lambda canal=0: JPEG  # type: ignore[method-assign]
    enviadas: list[tuple[str, str]] = []

    def mostrar(caminho: Path, titulo: str) -> str:
        enviadas.append((caminho.name, titulo))
        return "celular"

    vigia = Vigia(dispositivo, tmp_path / "fotos", mostrar)
    vigia.lentes = 3
    vigia._ao_alarme({"Event": "appEventHumanDetectAlarm", "Status": "Start", "Channel": 1})
    limite = time.monotonic() + 2
    while not enviadas and time.monotonic() < limite:
        time.sleep(0.01)
    assert len(enviadas) == 1
    assert enviadas[0][0].endswith("-lente2.jpg")
    assert enviadas[0][1] == "Movimento · Lente 2"
    vigia.fotos_agora()  # quem pede pelo painel ou pela voz decide se quer ver
    assert len(enviadas) == 1


def test_enviar_desligado_guarda_sem_mandar_ao_celular(tmp_path: Path) -> None:
    dispositivo = camera.Camera(tmp_path / "camera.json")
    dispositivo.guardar("127.0.0.1", "admin", "segredo", enviar=False)
    dispositivo.guardar("127.0.0.1", "admin", "")  # salvar de novo mantém a escolha
    dispositivo.foto = lambda canal=0: JPEG  # type: ignore[method-assign]
    enviadas: list[str] = []

    def mostrar(_caminho: Path, titulo: str) -> str:
        enviadas.append(titulo)
        return "celular"

    vigia = Vigia(dispositivo, tmp_path / "fotos", mostrar)
    vigia._ao_alarme({"Event": "MotionDetect", "Status": "Start"})
    assert len(_esperar_fotos(tmp_path / "fotos")) == 1
    time.sleep(0.1)
    assert enviadas == []
    assert dispositivo.para_tela()["enviar"] is False
