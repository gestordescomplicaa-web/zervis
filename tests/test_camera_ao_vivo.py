"""O vídeo ao vivo da câmera (ADR 0101): o ffmpeg montado sem a senha nos argumentos, os quadros
separados, o limite de quem assiste, o fim ao sair e a rota do painel só para quem entrou."""

import http.client
import io
import os
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


class Processo:
    """O ffmpeg falso: devolve os bytes em pedaços que cortam os JPEG no meio."""

    def __init__(self, dados: bytes) -> None:
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
        self.manifestos: list[str] = []
        self.processos: list[Processo] = []

    def __call__(self, comando: list[str], leitura: int) -> Processo:
        self.comandos.append(comando)
        self.manifestos.append(os.read(leitura, 4096).decode())
        processo = Processo(self.dados)
        self.processos.append(processo)
        return processo


def _camera(tmp_path: Path, girar: list[int] | None = None) -> camera.Camera:
    dispositivo = camera.Camera(tmp_path / "camera.json")
    dispositivo.guardar("192.168.0.20", "zervis", SENHA, girar=girar or [])
    return dispositivo


def _ao_vivo(tmp_path: Path, lancar: Lancador, girar: list[int] | None = None) -> Any:
    return camera_ao_vivo.AoVivo(
        _camera(tmp_path, girar), lancar=lancar, achar_ffmpeg=lambda: "/usr/bin/ffmpeg"
    )


def test_quadros_inteiros_mesmo_cortados_no_meio() -> None:
    fluxo = JPEG_A + b"lixo" + JPEG_B
    pedacos = [fluxo[i : i + 7] for i in range(0, len(fluxo), 7)]
    assert list(camera_ao_vivo.quadros(iter(pedacos))) == [JPEG_A, JPEG_B]


def test_transmite_partes_multipart_da_lente_pedida(tmp_path: Path) -> None:
    lancar = Lancador()
    partes = list(_ao_vivo(tmp_path, lancar, girar=[2]).transmitir(2, "leve"))
    assert partes == [camera_ao_vivo.parte(JPEG_A), camera_ao_vivo.parte(JPEG_B)]
    assert partes[0].startswith(b"--quadro\r\nContent-Type: image/jpeg\r\n")
    (comando,) = lancar.comandos
    assert SENHA not in " ".join(comando)  # a senha vai só pelo descritor
    assert "rtp" in comando[comando.index("-protocol_whitelist") + 1].split(",")
    assert "option rtsp_transport tcp" in lancar.manifestos[0]  # o RTP pelo TCP, sem perdas
    assert "hflip,vflip" in comando  # a lente 2 está marcada para girar
    assert "channel=2&stream=1.sdp" in lancar.manifestos[0]  # lente 2, o fluxo leve
    assert lancar.processos[0].morto


def test_a_lente_sem_giro_e_a_qualidade_alta(tmp_path: Path) -> None:
    lancar = Lancador()
    list(_ao_vivo(tmp_path, lancar, girar=[2]).transmitir(1))
    assert "hflip,vflip" not in lancar.comandos[0]
    assert "channel=1&stream=0.sdp" in lancar.manifestos[0]


def test_no_maximo_tres_assistindo_e_sair_libera_a_vaga(tmp_path: Path) -> None:
    lancar = Lancador()
    ao_vivo = _ao_vivo(tmp_path, lancar)
    abertos = [ao_vivo.transmitir(1) for _ in range(camera_ao_vivo.MAXIMO)]
    for fluxo in abertos:
        next(fluxo)
    with pytest.raises(camera_ao_vivo.AoVivoErro, match="3 pessoas"):
        ao_vivo.transmitir(1)
    abertos[0].close()  # a pessoa saiu da página: o ffmpeg dela termina
    assert lancar.processos[0].morto
    next(ao_vivo.transmitir(1))


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
    lancar = Lancador()
    ao_vivo = camera_ao_vivo.AoVivo(_camera(tmp_path), lancar=lancar, achar_ffmpeg=lambda: ffmpeg)
    with pytest.raises(camera_ao_vivo.AoVivoErro, match=erro):
        ao_vivo.transmitir(lente, qualidade)
    assert lancar.comandos == []


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
    assert set(fluxos) == {"camera/ao-vivo"}
    with pytest.raises(PedidoInvalido, match="não configurada"):
        fluxos["camera/ao-vivo"]({"lente": "1"})
