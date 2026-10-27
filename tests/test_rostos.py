"""Rostos e o modo de escuta (ADR 0021): o Zé ativo sem depender da janela no Hyprland."""

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.portal.acoes import Acoes
from zervis.portal.servidor import PedidoInvalido
from zervis.presenca import hyprland
from zervis.presenca import modo as escuta
from zervis.presenca.rostos import Rostos
from zervis.transporte import local


def test_ativo_enquanto_houver_um_rosto() -> None:
    mudancas: list[bool] = []
    r = Rostos(mudancas.append)
    r.marcar("janela", False)
    r.marcar("sempre", True)
    r.marcar("janela", True)
    r.marcar("sempre", False)
    assert mudancas == [False, True]  # a janela ainda segura o Zé ativo
    r.marcar("janela", False)
    assert mudancas == [False, True, False] and r.ativos == frozenset()


def test_padrao_segue_a_maquina(tmp_path: Path) -> None:
    arquivo = tmp_path / "escuta.json"
    assert escuta.ler(tem_janela=True, arquivo=arquivo) == "janela"
    assert escuta.ler(tem_janela=False, arquivo=arquivo) == "sempre"


def test_janela_sem_hyprland_vale_sempre(tmp_path: Path) -> None:
    arquivo = tmp_path / "escuta.json"
    escuta.gravar("janela", arquivo)
    assert escuta.ler(tem_janela=True, arquivo=arquivo) == "janela"
    assert escuta.ler(tem_janela=False, arquivo=arquivo) == "sempre"
    escuta.gravar("sempre", arquivo)
    assert escuta.ler(tem_janela=True, arquivo=arquivo) == "sempre"
    with pytest.raises(ValueError, match="desconhecido"):
        escuta.gravar("nunca", arquivo)
    arquivo.write_text("{quebrado")
    assert escuta.ler(tem_janela=True, arquivo=arquivo) == "janela"


def test_hyprland_disponivel_so_com_instancia_e_hyprctl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("zervis.presenca.hyprland.shutil.which", lambda nome: "/usr/bin/hyprctl")
    assert not hyprland.disponivel(tmp_path / "hypr")
    (tmp_path / "hypr" / "assinatura").mkdir(parents=True)
    assert hyprland.disponivel(tmp_path / "hypr")
    monkeypatch.setattr("zervis.presenca.hyprland.shutil.which", lambda nome: None)
    assert not hyprland.disponivel(tmp_path / "hypr")


def _fontes(saida: str) -> Any:
    def executar(comando: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(comando, 0, stdout=saida, stderr="")

    return executar


def test_microfone_configurado_ou_o_padrao_do_sistema(monkeypatch: pytest.MonkeyPatch) -> None:
    linhas = "52\tomarchy_mic_fx\tPipeWire\ts16le 1ch 48000Hz\tRUNNING\n"
    monkeypatch.setattr("zervis.transporte.local.subprocess.run", _fontes(linhas))
    assert local.fonte("omarchy_mic_fx") == "omarchy_mic_fx"
    monkeypatch.setattr(
        "zervis.transporte.local.subprocess.run", _fontes("60\talsa_input.pci\tPipeWire\n")
    )
    assert local.fonte("omarchy_mic_fx") == local.PADRAO
    assert local.fonte("") == local.PADRAO


def test_sem_pactl_tenta_o_configurado(monkeypatch: pytest.MonkeyPatch) -> None:
    def falhar(*_: Any, **__: Any) -> Any:
        raise FileNotFoundError("pactl")

    monkeypatch.setattr("zervis.transporte.local.subprocess.run", falhar)
    assert local.fonte("omarchy_mic_fx") == "omarchy_mic_fx"


def test_painel_troca_a_escuta(tmp_path: Path) -> None:
    trocas: list[str] = []

    def mudar(modo: str) -> str:
        if modo == "janela":
            raise ValueError("Requer Hyprland.")
        trocas.append(modo)
        return "Escuta: sempre."

    acoes = Acoes(SimpleNamespace(mudar_escuta=mudar), tmp_path / "l", tmp_path / "t")
    assert acoes.mudar_escuta({"modo": "sempre"}) == {"modo": "sempre", "aviso": "Escuta: sempre."}
    with pytest.raises(PedidoInvalido, match="Requer Hyprland"):
        acoes.mudar_escuta({"modo": "janela"})
    with pytest.raises(PedidoInvalido, match="desconhecido"):
        acoes.mudar_escuta({"modo": "nunca"})
    assert trocas == ["sempre"]
