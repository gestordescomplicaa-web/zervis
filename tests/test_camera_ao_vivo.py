"""O vídeo ao vivo da câmera (ADR 0101): a lente pedida pelo DVRIP, o ffmpeg sem a senha, os
quadros separados, o limite de vídeos, o fim ao sair e a rota do painel só para quem entrou."""

import http.client
import io
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from zervis import camera, camera_ao_vivo
from zervis.portal.senha import Acesso
from zervis.portal.servidor import COOKIE, PedidoInvalido, Portal

JPEG_A = b"\xff\xd8" + b"a" * 50 + b"\xff\xd9"
JPEG_B = b"\xff\xd8" + b"b" * 70 + b"\xff\xd9"
SENHA = "senha-de-teste"


class Entrada:
    """A entrada do ffmpeg falso: guarda o H.265 que chegou."""

    def __init__(self) -> None:
        self.recebido = b""
        self.fechada = threading.Event()

    def write(self, dados: bytes) -> None:
        self.recebido += dados

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.fechada.set()


class Processo:
    """O ffmpeg falso: devolve JPEG em pedaços que cortam os quadros no meio."""

    def __init__(self, dados: bytes) -> None:
        self.stdin = Entrada()
        self.stdout = io.BytesIO(dados)
        self.morto = False

    def kill(self) -> None:
        self.morto = True

    def wait(self, timeout: float | None = None) -> int:
        return 0


class Lancador:
    def __init__(self, dados: bytes = JPEG_A + JPEG_B) -> None:
        self.dados = dados
        self.comandos: list[list[str]] = []
        self.processos: list[Processo] = []

    def __call__(self, comando: list[str]) -> Processo:
        self.comandos.append(comando)
        processo = Processo(self.dados)
        self.processos.append(processo)
        return processo


class VideoFalso:
    def __init__(self, blocos: list[bytes]) -> None:
        self.blocos = blocos
        self.fechado = False

    def __iter__(self) -> Iterator[bytes]:
        return iter(self.blocos)

    def fechar(self) -> None:
        self.fechado = True


class CameraFalsa(camera.Camera):
    """O cadastro de verdade, com o vídeo de cada lente falso."""

    def __init__(self, arquivo: Path, erro: str = "") -> None:
        super().__init__(arquivo)
        self.erro = erro
        self.pedidos: list[tuple[int, bool]] = []
        self.videos: list[VideoFalso] = []

    def video(self, canal: int = 0, principal: bool = True) -> Any:
        if self.erro:
            raise camera.CameraErro(self.erro)
        self.pedidos.append((canal, principal))
        self.videos.append(VideoFalso([b"h265-1", b"h265-2"]))
        return self.videos[-1]


def _camera(tmp_path: Path, girar: list[int] | None = None, erro: str = "") -> CameraFalsa:
    dispositivo = CameraFalsa(tmp_path / "camera.json", erro)
    dispositivo.guardar("192.168.0.20", "zervis", SENHA, girar=girar or [])
    return dispositivo


def _ao_vivo(dispositivo: camera.Camera, lancar: Lancador) -> Any:
    return camera_ao_vivo.AoVivo(dispositivo, lancar=lancar, achar_ffmpeg=lambda: "/usr/bin/ffmpeg")


def test_quadros_inteiros_mesmo_cortados_no_meio() -> None:
    fluxo = JPEG_A + b"lixo" + JPEG_B
    pedacos = [fluxo[i : i + 7] for i in range(0, len(fluxo), 7)]
    assert list(camera_ao_vivo.quadros(iter(pedacos))) == [JPEG_A, JPEG_B]


def test_a_lente_pedida_pelo_dvrip_e_o_ffmpeg_sem_senha(tmp_path: Path) -> None:
    lancar, dispositivo = Lancador(), _camera(tmp_path, girar=[2])
    partes = list(_ao_vivo(dispositivo, lancar).transmitir(2, "leve"))
    assert partes == [camera_ao_vivo.parte(JPEG_A), camera_ao_vivo.parte(JPEG_B)]
    assert partes[0].startswith(b"--quadro\r\nContent-Type: image/jpeg\r\n")
    assert dispositivo.pedidos == [(1, False)]  # lente 2 (canal 1), o fluxo leve
    (comando,) = lancar.comandos
    assert SENHA not in " ".join(comando) and "rtsp" not in " ".join(comando)
    assert comando[comando.index("-f") + 1] == "hevc"  # o H.265 entra pela entrada padrão
    assert "hflip,vflip" in comando  # a lente 2 está marcada para girar
    processo = lancar.processos[0]
    assert processo.stdin.fechada.wait(2) and processo.stdin.recebido == b"h265-1h265-2"
    assert processo.morto and dispositivo.videos[0].fechado


def test_a_lente_sem_giro_e_a_qualidade_alta(tmp_path: Path) -> None:
    lancar, dispositivo = Lancador(), _camera(tmp_path, girar=[2])
    list(_ao_vivo(dispositivo, lancar).transmitir(1))
    assert "hflip,vflip" not in lancar.comandos[0]
    assert dispositivo.pedidos == [(0, True)]


def test_no_maximo_seis_videos_e_sair_libera_a_vaga(tmp_path: Path) -> None:
    lancar, dispositivo = Lancador(), _camera(tmp_path)
    ao_vivo = _ao_vivo(dispositivo, lancar)
    abertos = [ao_vivo.transmitir(1) for _ in range(camera_ao_vivo.MAXIMO)]
    for fluxo in abertos:
        next(fluxo)
    with pytest.raises(camera_ao_vivo.AoVivoErro, match="6 vídeos"):
        ao_vivo.transmitir(1)
    abertos[0].close()  # a pessoa saiu da página: a conexão e o ffmpeg dela terminam
    assert lancar.processos[0].morto and dispositivo.videos[0].fechado
    next(ao_vivo.transmitir(1))


def test_camera_sem_video_explica_e_devolve_a_vaga(tmp_path: Path) -> None:
    lancar = Lancador()
    ao_vivo = _ao_vivo(_camera(tmp_path, erro="Sem vídeo da câmera agora."), lancar)
    for _ in range(camera_ao_vivo.MAXIMO + 1):
        with pytest.raises(camera_ao_vivo.AoVivoErro, match="Sem vídeo"):
            ao_vivo.transmitir(1)
    assert lancar.comandos == []


@pytest.mark.parametrize(
    ("lente", "qualidade", "ffmpeg", "erro"),
    [
        (1, "alta", None, "Instale o ffmpeg"),
        (0, "alta", "/usr/bin/ffmpeg", "Lente inválida"),
        (1, "media", "/usr/bin/ffmpeg", "Qualidade inválida"),
    ],
)
def test_erros_antes_de_abrir(
    tmp_path: Path, lente: int, qualidade: str, ffmpeg: str | None, erro: str
) -> None:
    lancar, dispositivo = Lancador(), _camera(tmp_path)
    ao_vivo = camera_ao_vivo.AoVivo(dispositivo, lancar=lancar, achar_ffmpeg=lambda: ffmpeg)
    with pytest.raises(camera_ao_vivo.AoVivoErro, match=erro):
        ao_vivo.transmitir(lente, qualidade)
    assert lancar.comandos == [] and dispositivo.pedidos == []


def test_sem_camera_cadastrada(tmp_path: Path) -> None:
    ao_vivo = camera_ao_vivo.AoVivo(camera.Camera(tmp_path / "nada.json"))
    with pytest.raises(camera_ao_vivo.AoVivoErro, match="não configurada"):
        ao_vivo.transmitir(1)


def test_a_foto_de_reserva_tambem_aceita_rtp() -> None:
    assert "rtp" in camera.PROTOCOLOS_RTSP.split(",")


# --- a rota do painel ------------------------------------------------------------------------


@pytest.fixture
def painel(tmp_path: Path) -> Iterator[tuple[Portal, str, list[dict[str, str]]]]:
    pedidos: list[dict[str, str]] = []

    def fluxo(consulta: dict[str, str]) -> tuple[str, Iterator[bytes]]:
        pedidos.append(consulta)
        if consulta.get("lente") == "9":
            raise PedidoInvalido("Lente inválida.")
        return camera_ao_vivo.TIPO, iter([camera_ao_vivo.parte(JPEG_A)])

    acesso = Acesso(tmp_path / "painel.json", tmp_path / "acessos.json")
    acesso.definir("uma senha boa")
    cookie, _ = acesso.entrar("uma senha boa", lembrar=False)
    p = Portal({}, {}, porta=0, acesso=acesso, servidor=True, fluxos={"camera/ao-vivo": fluxo})
    p.permitir("ze.exemplo.invalid")
    p.iniciar()
    yield p, f"{COOKIE}={cookie}", pedidos
    p.parar()


def _pedir(p: Portal, caminho: str, cab: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", p.porta, timeout=5)
    fora = {"Host": "ze.exemplo.invalid", "Cf-Connecting-Ip": "203.0.113.7"}
    conn.request("GET", caminho, headers={**fora, **cab})
    r = conn.getresponse()
    resposta = (r.status, dict(r.getheaders()), r.read())
    conn.close()
    return resposta


def test_a_rota_so_para_quem_entrou(painel: Any) -> None:
    p, cookie, pedidos = painel
    status, cab, _ = _pedir(p, "/fluxo/camera/ao-vivo?lente=1", {})
    assert status == 303 and cab["Location"] == "/entrar" and pedidos == []
    status, cab, corpo = _pedir(
        p, "/fluxo/camera/ao-vivo?lente=2&qualidade=leve", {"Cookie": cookie}
    )
    assert status == 200 and cab["Content-Type"] == camera_ao_vivo.TIPO
    assert corpo == camera_ao_vivo.parte(JPEG_A)
    assert pedidos == [{"lente": "2", "qualidade": "leve"}]


def test_a_rota_explica_o_erro(painel: Any) -> None:
    p, cookie, _ = painel
    status, _, corpo = _pedir(p, "/fluxo/camera/ao-vivo?lente=9", {"Cookie": cookie})
    assert status == 400 and "Lente inválida." in corpo.decode()
    assert _pedir(p, "/fluxo/outra-coisa", {"Cookie": cookie})[0] == 404


def test_o_painel_de_verdade_registra_a_transmissao(tmp_path: Path) -> None:
    """As ações montadas como na subida do Zé: cada transmissão existe e chega à câmera."""
    from types import SimpleNamespace

    from zervis.portal.acoes import Acoes

    acoes = Acoes(SimpleNamespace(camera=camera.Camera(tmp_path / "nada.json")), tmp_path, tmp_path)
    fluxos = acoes.fluxos()
    assert set(fluxos) == {"camera/ao-vivo", "marketing/video"}  # o vídeo da Marketing (ADR 0106)
    with pytest.raises(PedidoInvalido, match="Vídeo"):
        fluxos["marketing/video"]({"id": "../x"})
    with pytest.raises(PedidoInvalido, match="não configurada"):
        fluxos["camera/ao-vivo"]({"lente": "1"})
