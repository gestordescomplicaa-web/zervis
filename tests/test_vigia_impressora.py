"""O vigia da impressora 3D e a impressão mais segura (ADR 0085): o motivo do erro pela tabela da
Bambu, os avisos de cada mudança, o retrato montado com o que chega, a foto da câmera, o suporte
decidido pela peça e a prévia do fatiamento. Nada fala com uma impressora de verdade."""

import asyncio
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from zervis import fatiador, projetos3d
from zervis.cerebro.ferramentas import LIVRES
from zervis.cerebro.ferramentas import projetos3d as g_projetos3d
from zervis.impressora3d import Impressora3D, resumir
from zervis.impressora_vigia import Vigia, eventos, motivo, nome_da_tarefa, tabela

TEXTOS = {
    "07FF8011": "External filament has run out; please load a new filament.",
    "03008017": "Foreign objects detected on heatbed. Please check and clean the heatbed.",
    "0300400C": "The task was canceled.",
}


def base(**campos: Any) -> dict[str, Any]:
    r = {"estado": "imprimindo", "camada": 5, "camadas": 100, "tarefa": "Suporte-celular.3mf",
         "erro": ""}  # fmt: skip
    return {**r, **campos}


def test_a_tabela_da_bambu_em_portugues_ou_por_categoria(tmp_path: Path) -> None:
    def gravar(nome: str, ecode: str, intro: str) -> None:
        dados = {"data": {"device_error": {"x": [{"ecode": ecode, "intro": intro}]}}}
        (tmp_path / nome).write_text(json.dumps(dados))

    gravar("hms_en_039.json", "07FF8011", TEXTOS["07FF8011"])
    assert tabela("039", [tmp_path]) == ({"07FF8011": TEXTOS["07FF8011"]}, "en")
    assert motivo("07FF8011", *tabela("039", [tmp_path])) == (
        "acabou o filamento",
        TEXTOS["07FF8011"],
    )
    assert motivo("12345678", {}, "en") == ("um erro, código 1234_5678", "Código 1234_5678")
    gravar("hms_pt-BR_039.json", "07FF8011", "O filamento externo acabou.")
    textos, idioma = tabela("039", [tmp_path])
    assert idioma == "pt" and motivo("07FF8011", textos, idioma)[0] == "O filamento externo acabou"
    assert tabela("093", [tmp_path]) == ({}, "")


def test_cada_mudanca_vira_o_aviso_certo() -> None:
    def falas(antes: dict[str, Any] | None, agora: dict[str, Any]) -> list[tuple[str, bool]]:
        return [(e["fala"], e["foto"]) for e in eventos(antes, agora, TEXTOS, "en")]

    assert falas(None, base(estado="pausada", erro="07FF8011")) == []  # o ponto de partida
    assert falas(base(), base(estado="pausada", erro="07FF8011")) == [
        ("A impressão de Suporte celular pausou: acabou o filamento.", True)
    ]
    assert falas(base(), base(estado="pausada")) == [
        ("A impressão de Suporte celular está pausada.", False)
    ]
    assert falas(base(estado="pausada"), base()) == [
        ("A impressão de Suporte celular voltou.", False)
    ]
    assert falas(base(), base(estado="cancelada", erro="0300400C")) == [
        ("A impressão de Suporte celular foi cancelada.", False)
    ]
    assert falas(base(), base(estado="falhou", erro="03008017")) == [
        ("A impressão de Suporte celular falhou: há algo sobre a mesa.", True)
    ]
    assert falas(base(), base(estado="concluída")) == [
        ("A impressão de Suporte celular terminou.", True)
    ]
    assert falas(base(estado="ociosa"), base(estado="concluída")) == []  # nada imprimia
    assert falas(base(camada=1), base(camada=2)) == [
        ("A primeira camada de Suporte celular está pronta.", True)
    ]
    assert falas(base(camada=2), base(camada=3)) == []
    assert falas(base(), base(erro="03008017")) == [
        ("A impressora avisou: há algo sobre a mesa.", True)
    ]
    assert nome_da_tarefa("") == "peça"


def test_o_cancelamento_aparece_como_cancelado() -> None:
    falhou = {"print": {"gcode_state": "FAILED", "print_error": 0x0300400C}}
    assert resumir(falhou)["estado"] == "cancelada" and resumir(falhou)["erro"] == "0300400C"
    erro = {"print": {"gcode_state": "FAILED", "print_error": 0x03008017,
                      "hms": [{"attr": 0x0C000300, "code": 0x0003000B}]}}  # fmt: skip
    assert resumir(erro)["estado"] == "falhou" and resumir(erro)["hms"] == ["0C0003000003000B"]


def test_o_vigia_junta_o_que_chega_avisa_e_guarda_a_foto(tmp_path: Path) -> None:
    impressora = Impressora3D(tmp_path / "i.json", lambda *a: {})
    impressora.guardar("192.168.0.20", "03900A000000001", "12345678")
    avisos: list[str] = []
    vigia = Vigia(
        impressora, avisos.append, tmp_path / "fotos",
        textos=lambda modelo: (TEXTOS, "en"), fotografar=lambda c: b"\xff\xd8 foto",
    )  # fmt: skip
    vigia._conexao = impressora.conexao()
    vigia._tabela = (TEXTOS, "en")
    mostradas: list[tuple[bytes, str]] = []  # a foto na tela de quem fala (ADR 0086)

    def mostrar(foto: Path, titulo: str) -> str:
        mostradas.append((foto.read_bytes(), titulo))
        return ""

    impressora.mostrar = mostrar
    pedaco = {"print": {"gcode_state": "RUNNING", "layer_num": 1, "total_layer_num": 80,
                        "subtask_name": "Suporte-celular.3mf", "nozzle_temper": 210}}  # fmt: skip
    vigia.receber(json.dumps(pedaco).encode())
    assert vigia.retrato() and impressora.status()["estado"] == "imprimindo"  # pelo vigia
    vigia.receber(json.dumps({"print": {"layer_num": 2}}).encode())  # só o que mudou
    vigia.receber(
        json.dumps({"print": {"gcode_state": "PAUSE", "print_error": 0x07FF8011}}).encode()
    )
    vigia.receber(b"lixo")
    for _ in range(100):
        if len(avisos) == 2 and len(vigia.avisos) == 2 and len(mostradas) == 2:
            break
        asyncio.run(asyncio.sleep(0.01))
    assert sorted(avisos) == [
        "A impressão de Suporte celular pausou: acabou o filamento.",
        "A primeira camada de Suporte celular está pronta.",
    ]
    fotos = list((tmp_path / "fotos").glob("*.jpg"))
    assert fotos and fotos[0].read_bytes() == b"\xff\xd8 foto"
    assert all(a["foto"] for a in vigia.avisos)
    assert sorted(titulo for _, titulo in mostradas) == sorted(avisos)  # cada aviso, com a foto
    assert {foto for foto, _ in mostradas} == {b"\xff\xd8 foto"}
    assert [a["fala"] for a in impressora.avisos()] == [a["fala"] for a in vigia.avisos]


def test_a_foto_pela_voz(tmp_path: Path) -> None:
    impressora = Impressora3D(tmp_path / "i.json", lambda *a: {})
    impressora.guardar("192.168.0.20", "03900A000000001", "12345678")
    Vigia(impressora, lambda t: None, tmp_path / "fotos", fotografar=lambda c: b"\xff\xd8 foto")
    projetos = projetos3d.Projetos3D(tmp_path / "p", tmp_path / "a", tmp_path / "a.json")
    fs: dict[str, Any] = {
        f.name: f.handler for f in g_projetos3d.ferramentas(projetos, None, None, None, impressora)
    }
    r = asyncio.run(fs["impressora_foto"]({}))
    assert r["content"][1]["type"] == "image" and r["content"][1]["mimeType"] == "image/jpeg"
    assert "não foi enviada" in r["content"][0]["text"]  # ninguém fala de outro aparelho
    # "Me manda uma foto da impressão", pelo celular (ADR 0086): a foto vai à tela de quem pediu.
    enviadas: list[tuple[bytes, str]] = []

    def mostrar(foto: Path, titulo: str) -> str:
        enviadas.append((foto.read_bytes(), titulo))
        return "celular"

    impressora.mostrar = mostrar
    r = asyncio.run(fs["impressora_foto"]({}))
    assert enviadas == [(b"\xff\xd8 foto", "Câmera da impressora")]
    assert "enviada ao celular" in r["content"][0]["text"]
    assert "mcp__jarvis__impressora_foto" in LIVRES


# ---- imprimir mais seguro ----


def test_suporte_so_para_o_que_fica_no_ar() -> None:
    mesa = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]]], float)
    inclinada = np.array([[[0, 0, 10], [10, 10, 5], [10, 0, 10]]], float)  # 63° para baixo
    teto = np.array([[[0, 0, 8], [0, 10, 8], [10, 0, 8]]], float)  # reto: a impressora faz ponte
    assert projetos3d.balanco_mm2(np.concatenate([mesa, inclinada])) == pytest.approx(55.9, 0.01)
    assert projetos3d.balanco_mm2(np.concatenate([mesa, teto])) == 0
    assert projetos3d.balanco_mm2(inclinada) == 0  # sozinha, ela é a mesa
    dados = {"minutos": 41, "gramas": 25.4, "filamento": "Bambu PLA Lite @BBL A1", "bandeja": 1}
    assert projetos3d.fala_da_fatia({**dados, "suporte": True}).endswith(
        "da bandeja 2, com suporte nas partes no ar."
    )


GCODE = """; HEADER
M83
; CHANGE_LAYER
; Z_HEIGHT: 0.2
; FEATURE: Outer wall
G1 X10 Y10 F3000
G1 X20 Y10 E.5
G1 X20 Y20 E.5
G1 X30 Y30
; FEATURE: Support
G1 X40 Y30 E.3
; CHANGE_LAYER
; Z_HEIGHT: 0.4
; FEATURE: Sparse infill
G1 X40 Y40 E.2
G1 E-.8
"""


def test_a_previa_do_fatiamento(tmp_path: Path) -> None:
    arquivo = tmp_path / "fatiado.3mf"
    with zipfile.ZipFile(arquivo, "w") as z:
        z.writestr("Metadata/plate_1.gcode", GCODE)
    t = fatiador.trajetos(arquivo)
    assert t["total_camadas"] == 2 and t["passo"] == 1
    assert t["camadas"][0] == {
        "z": 0.2,
        "linhas": [["parede", 100, 100, 200, 100, 200, 200], ["suporte", 300, 300, 400, 300]],
    }
    assert t["camadas"][1]["linhas"] == [["preenchimento", 400, 300, 400, 400]]
    assert fatiador.trajetos(arquivo, maximo=1)["passo"] == 7  # 7 pontos: uma camada a cada 7
