"""Fatiar e imprimir (ADR 0083): a conexão guardada sem o código voltar para a tela, o status em
português, imprimir só com a impressora parada e com o arquivo certo, o aviso do fim, o perfil
completo do Bambu Studio e o caminho do projeto até a impressora. Nada aqui fala com uma
impressora nem roda o Bambu Studio de verdade."""

import json
import stat
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_projetos3d import cubo, stl_binario  # type: ignore[import-not-found]

from zervis import fatiador, impressora3d, projetos3d
from zervis.cerebro import claude
from zervis.cerebro.ferramentas import LIVRES
from zervis.impressora3d import Conexao, Impressora3D, ImpressoraErro
from zervis.portal.acoes.pagina import Servicos
from zervis.portal.acoes.projetos3d import AcoesProjetos3D
from zervis.portal.servidor import PedidoInvalido

PARADA = {
    "print": {
        "gcode_state": "IDLE", "nozzle_temper": 28.25, "bed_temper": 27.9,
        "ams": {"ams": [{"id": "0", "tray": [{"id": "0"}, {"id": "1", "tray_type": "PLA",
                "tray_sub_brands": "PLA Lite", "tray_color": "FFFFFFFF"}]}]},
        "vt_tray": {"tray_type": "PETG"},
    }
}  # fmt: skip


class Mqtt:
    """A impressora de mentira: devolve os retratos na ordem e guarda os pedidos."""

    def __init__(self, *retratos: dict[str, Any]) -> None:
        self.retratos = list(retratos)
        self.pedidos: list[dict[str, Any]] = []

    def __call__(self, c: Conexao, pedidos: list[dict[str, Any]], espera: float) -> dict[str, Any]:
        self.pedidos += pedidos
        return self.retratos.pop(0) if len(self.retratos) > 1 else self.retratos[0]


def impressora(tmp_path: Path, mqtt: Mqtt, enviados: list[Any] | None = None) -> Impressora3D:
    i = Impressora3D(
        tmp_path / "impressora3d.json",
        mqtt,
        lambda c, origem, nome: (enviados if enviados is not None else []).append((origem, nome)),
    )
    i.guardar("192.168.0.20", "03900a000000001", "12345678")
    return i


def test_a_conexao_e_de_quem_usa_e_o_codigo_nao_volta(tmp_path: Path) -> None:
    i = impressora(tmp_path, Mqtt(PARADA))
    arquivo = tmp_path / "impressora3d.json"
    assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
    assert i.para_tela() == {
        "configurada": True, "ip": "192.168.0.20", "serie": "03900A000000001", "modelo": "A1",
    }  # fmt: skip
    i.guardar("192.168.0.21", "03900A000000001", "")  # código vazio: fica o de antes
    assert i.conexao() == Conexao("192.168.0.21", "03900A000000001", "12345678")
    for ip, serie, codigo in (
        ("8.8.8.8", "03900A000000001", "12345678"),  # fora da rede local
        ("192.168.0.20", "x", "12345678"),
        ("192.168.0.20", "03900A000000001", "1; rm"),
        ("nada", "03900A000000001", "12345678"),
    ):
        with pytest.raises(ImpressoraErro):
            i.guardar(ip, serie, codigo)


def test_o_numero_de_serie_vem_do_certificado() -> None:
    der = (
        b"\x30\x82"
        + b"\x55\x04\x03\x0c\x06BBL CA"
        + b"\x00\x01"
        + b"\x55\x04\x03\x0c\x0f03900A000000001"
    )
    assert impressora3d.nomes_do_certificado(der) == ["BBL CA", "03900A000000001"]


def test_o_status_em_portugues(tmp_path: Path) -> None:
    s = impressora(tmp_path, Mqtt(PARADA)).status()
    assert s["estado"] == "ociosa" and s["bico_c"] == 28
    assert s["bandejas"] == [{"indice": 1, "tipo": "PLA", "marca": "PLA Lite", "cor": "#FFFFFF"}]
    assert s["externo"] == "PETG"


def test_imprime_so_parada_e_com_o_arquivo_certo(tmp_path: Path) -> None:
    enviados: list[Any] = []
    mqtt = Mqtt(PARADA)
    i = impressora(tmp_path, mqtt, enviados)
    i.acompanhar = lambda nome, intervalo_s=0: None  # type: ignore[method-assign]
    fatiado = tmp_path / "fatiado.3mf"
    fatiado.write_bytes(b"3mf")
    assert i.imprimir(fatiado, "Suporte celular", 1) == {"enviado": "Suporte-celular.3mf"}
    assert enviados == [(fatiado, "Suporte-celular.3mf")]
    pedido = mqtt.pedidos[-1]["print"]
    assert (
        pedido["command"] == "project_file"
        and pedido["url"] == "file:///sdcard/Suporte-celular.3mf"
    )
    assert pedido["use_ams"] is True and pedido["ams_mapping"] == [1]
    ocupada = impressora(tmp_path, Mqtt({"print": {**PARADA["print"], "gcode_state": "RUNNING"}}))
    with pytest.raises(ImpressoraErro, match="imprimindo"):
        ocupada.imprimir(fatiado, "Outra", 1)


def test_comandos_e_o_aviso_do_fim(tmp_path: Path) -> None:
    mqtt = Mqtt(
        {"print": {"gcode_state": "RUNNING"}},
        {"print": {"gcode_state": "RUNNING"}},
        {"print": {"gcode_state": "FINISH"}},
    )
    i = impressora(tmp_path, mqtt)
    i.comando("pausar")
    assert mqtt.pedidos[-1] == {"print": {"sequence_id": "0", "command": "pause"}}
    with pytest.raises(ImpressoraErro):
        i.comando("explodir")
    avisos: list[str] = []
    i.ao_avisar = avisos.append
    i.acompanhar("Suporte", intervalo_s=0.01)
    fim = time.monotonic() + 3
    while not avisos and time.monotonic() < fim:
        time.sleep(0.01)
    assert avisos == ["A impressão de Suporte terminou."]


# ---- o fatiador ----


def test_o_perfil_completo_junta_o_que_herda() -> None:
    perfis = {
        "base": {"name": "base", "a": 1, "b": 1},
        "meio": {"name": "meio", "inherits": "base", "b": 2},
        "fim": {"name": "fim", "inherits": "meio", "c": 3},
    }
    assert fatiador.completo("fim", perfis) == {"name": "fim", "a": 1, "b": 2, "c": 3}
    with pytest.raises(fatiador.FatiadorErro):
        fatiador.completo("nao-existe", perfis)
    nomes = {"Bambu PLA Lite @BBL A1", "Generic PETG @BBL A1", "Bambu PLA Basic @BBL A1"}
    assert fatiador.filamento("A1", "PLA", "PLA Lite", nomes) == "Bambu PLA Lite @BBL A1"
    assert fatiador.filamento("A1", "PETG", "", nomes) == "Generic PETG @BBL A1"
    assert fatiador.filamento("A1", "ABS", "", nomes) == "Bambu PLA Basic @BBL A1"


def estudio(tmp_path: Path) -> fatiador.BambuStudio:
    perfis = tmp_path / "perfis"
    for pasta, nome in (
        ("machine", "Bambu Lab A1 0.4 nozzle"),
        ("process", "0.20mm Standard @BBL A1"),
        ("filament", "Bambu PLA Lite @BBL A1"),
    ):
        (perfis / pasta).mkdir(parents=True, exist_ok=True)
        (perfis / pasta / f"{nome}.json").write_text(json.dumps({"name": nome}))
    return fatiador.BambuStudio(("flatpak", "run", fatiador.FLATPAK), perfis, True)


def bambu(codigo: int = 0) -> Any:
    """O Bambu Studio de mentira: grava o result.json e o 3MF na pasta corrente."""
    chamadas: list[Any] = []

    def rodar(comando: list[str], cwd: Path, **_: Any) -> subprocess.CompletedProcess[str]:
        chamadas.append((comando, cwd))
        (cwd / "fatiado.3mf").write_bytes(b"3mf")
        placa = {"total_predication": 2465.7, "filaments": [{"total_used_g": 25.37}]}
        (cwd / "result.json").write_text(
            json.dumps({"return_code": codigo, "error_string": "x", "sliced_plates": [placa]})
        )
        return subprocess.CompletedProcess(comando, 0, "", "")

    rodar.chamadas = chamadas  # type: ignore[attr-defined]
    return rodar


def test_fatiar_roda_na_pasta_de_trabalho_e_le_o_resultado(tmp_path: Path) -> None:
    stl = tmp_path / "modelo.stl"
    stl.write_bytes(stl_binario(cubo()))
    rodar = bambu()
    f = fatiador.fatiar(
        stl, tmp_path / "trabalho", "A1", "PLA", "PLA Lite", estudio(tmp_path), rodar
    )
    assert (f.minutos, round(f.gramas, 1), f.filamento) == (41, 25.4, "Bambu PLA Lite @BBL A1")
    comando, cwd = rodar.chamadas[0]
    assert cwd == tmp_path / "trabalho"  # o result.json fica no trabalho, nunca na pasta do Zé
    assert comando[:3] == ["flatpak", "run", f"--filesystem={tmp_path / 'trabalho'}"]
    assert json.loads((cwd / "processo.json").read_text())["from"] == "User"
    with pytest.raises(fatiador.FatiadorErro, match="Modelo"):
        fatiador.fatiar(stl, tmp_path / "t2", "Ender 3", estudio=estudio(tmp_path), rodar=rodar)
    with pytest.raises(fatiador.FatiadorErro, match="recusou"):
        fatiador.fatiar(stl, tmp_path / "t3", "A1", "PLA", "PLA Lite", estudio(tmp_path), bambu(1))


# ---- do projeto à impressora ----


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> projetos3d.Projetos3D:
    projetos = projetos3d.Projetos3D(tmp_path / "p", tmp_path / "acervo", tmp_path / "a.json")
    pasta = Path(projetos.criar("Suporte celular", "peca", "8 cm")["pasta"])
    (pasta / "modelo.stl").write_bytes(stl_binario(cubo()))
    real = fatiador.fatiar
    monkeypatch.setattr(
        fatiador, "fatiar",
        lambda stl, trabalho, modelo, tipo, marca: real(
            stl, trabalho, modelo, tipo, marca, estudio(tmp_path), bambu()
        ),
    )  # fmt: skip
    return projetos


def test_do_projeto_a_impressora(projeto: projetos3d.Projetos3D, tmp_path: Path) -> None:
    enviados: list[Any] = []
    i = impressora(tmp_path, Mqtt(PARADA), enviados)
    i.acompanhar = lambda nome, intervalo_s=0: None  # type: ignore[method-assign]
    fatia = projetos3d.fatiar(projeto, i, "suporte-celular")
    assert fatia["bandeja"] == 1 and fatia["filamento"] == "Bambu PLA Lite @BBL A1"
    assert fatia["fala"] == "Leva 41 min e 25 g de PLA Lite da bandeja 2."
    lido = projeto.ler("suporte-celular")["arquivos"][0]
    assert lido["fatiado"] == {"minutos": 41, "gramas": 25.4, "filamento": "Bambu PLA Lite @BBL A1"}
    feito = projetos3d.imprimir(projeto, i, "suporte-celular")
    assert feito["fala"].startswith("Mandei Suporte celular para a impressora. Leva 41 min")
    assert enviados[0][1] == "Suporte-celular.3mf"
    sem = Impressora3D(tmp_path / "nada.json")
    with pytest.raises(projetos3d.Projeto3DErro, match="Configure"):
        projetos3d.fatiar(projeto, sem, "suporte-celular")


def test_a_pagina_so_imprime_confirmado_e_a_voz_pede_o_sim(
    projeto: projetos3d.Projetos3D, tmp_path: Path
) -> None:
    i = impressora(tmp_path, Mqtt(PARADA))
    i.acompanhar = lambda nome, intervalo_s=0: None  # type: ignore[method-assign]
    pagina = AcoesProjetos3D(
        SimpleNamespace(),
        Servicos(
            {
                "projetos3d": lambda: projeto,
                "impressora3d": lambda: i,
                "tela_tv": lambda: SimpleNamespace(ajustes=lambda: {"ligado": False}),
            }
        ),
    )
    assert pagina.projetos_3d()["impressora"]["modelo"] == "A1"
    assert "codigo" not in json.dumps(pagina.projetos_3d()["impressora"])
    assert pagina.fatiar_projeto_3d({"id": "suporte-celular"})["aviso"].startswith("Leva 41 min")
    with pytest.raises(PedidoInvalido, match="Confirme"):
        pagina.imprimir_projeto_3d({"id": "suporte-celular"})
    assert pagina.imprimir_projeto_3d({"id": "suporte-celular", "confirmado": True})["aviso"] == (
        "Enviado para a impressora."
    )
    assert {"mcp__jarvis__projeto3d_fatiar", "mcp__jarvis__impressora_status"} <= set(LIVRES)
    assert not {"mcp__jarvis__projeto3d_imprimir", "mcp__jarvis__impressora_comando"} & set(LIVRES)
    assert claude.descrever("mcp__jarvis__projeto3d_imprimir", {"projeto": "suporte-celular"}) == (
        "Vou mandar suporte-celular para a impressora."
    )
    assert claude.descrever("mcp__jarvis__impressora_comando", {"comando": "parar"}) == (
        "Vou cancelar a impressão."
    )
