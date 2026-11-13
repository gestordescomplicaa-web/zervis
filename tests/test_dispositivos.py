"""A lista de dispositivos (ADR 0089, fase 1): lida dos cadastros, sem migrar nada."""

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from zervis import camera, dispositivos
from zervis.camera_vigia import Vigia
from zervis.portal.acoes.dispositivos import AcoesDispositivos


class Impressora:
    def __init__(self, configurada: bool, viva: bool) -> None:
        self.configurada = configurada
        self.retrato_vivo: Callable[[], dict[str, Any]] | None = (
            (lambda: {"print": {}}) if viva else None
        )

    def para_tela(self) -> dict[str, Any]:
        if not self.configurada:
            return {"configurada": False, "ip": "", "serie": "", "modelo": ""}
        return {"configurada": True, "ip": "192.168.0.8", "serie": "03919C", "modelo": "A1"}


class TV:
    def __init__(self, ligado: bool) -> None:
        self.ligado = ligado

    def para_tela(self) -> dict[str, Any]:
        return {"ip_tv": "192.168.0.5", "ligado": self.ligado, "endereco": "", "aberta": False}


def test_sem_aparelho_a_lista_fica_vazia_e_todos_os_tipos_para_adicionar(tmp_path: Path) -> None:
    cam = camera.Camera(tmp_path / "camera.json")
    n = SimpleNamespace(
        camera=cam, vigia_camera=Vigia(cam, tmp_path / "fotos"),
        impressora3d=Impressora(False, False), tela_tv=TV(False),
    )  # fmt: skip
    r = AcoesDispositivos(None, n).dispositivos()  # type: ignore[arg-type]
    assert r["dispositivos"] == []
    assert [t["id"] for t in r["tipos"]] == ["camera", "impressora", "tv"]


def test_cada_aparelho_cadastrado_com_o_estado(tmp_path: Path) -> None:
    cam = camera.Camera(tmp_path / "camera.json")
    cam.guardar("192.168.0.2", "admin", "segredo")
    vigia = Vigia(cam, tmp_path / "fotos")
    vigia.lentes = 3
    lista = dispositivos.listar(cam, vigia, Impressora(True, viva=True), TV(True))
    assert lista == [
        {"id": "camera", "nome": "Câmera", "estado": "Sem conexão", "bom": False,
         "detalhe": "192.168.0.2 · 3 lentes"},
        {"id": "impressora", "nome": "Impressora 3D", "estado": "Conectada", "bom": True,
         "detalhe": "Bambu Lab A1 · 192.168.0.8"},
        {"id": "tv", "nome": "TV", "estado": "Ligado", "bom": False, "detalhe": "192.168.0.5"},
    ]  # fmt: skip
    n = SimpleNamespace(camera=cam, vigia_camera=vigia, impressora3d=Impressora(True, False),
                        tela_tv=TV(False))  # fmt: skip
    r = AcoesDispositivos(None, n).dispositivos()  # type: ignore[arg-type]
    assert [d["id"] for d in r["dispositivos"]] == ["camera", "impressora"]
    assert [t["id"] for t in r["tipos"]] == ["tv"]  # só o que falta adicionar
