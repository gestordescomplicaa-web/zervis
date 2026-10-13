"""O modelo do cérebro escolhido no painel (auditoria 2, achado 1): guardado, aplicado e só da
lista da conta."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from jarvis.cerebro import catalogo
from jarvis.config import carregar
from jarvis.nucleo.laco import Nucleo


def test_escolha_guardada_vale_sobre_a_config(tmp_path: Path) -> None:
    arquivo = tmp_path / "cerebro-modelos.json"
    assert catalogo.ler_modelos(arquivo) == {}
    catalogo.gravar_modelos(arquivo, {"claude": "claude-opus-5-5", "estranho": "x"})
    assert catalogo.ler_modelos(arquivo) == {"claude": "claude-opus-5-5"}
    cfg = carregar(tmp_path / "nao-existe.toml")
    catalogo.aplicar_modelos(cfg, {"claude": "claude-opus-5-5", "codex": "gpt-5.5"})
    assert (
        cfg["cerebro"]["modelo"] == "claude-opus-5-5"
        and cfg["cerebro"]["modelo_codex"] == "gpt-5.5"
    )


def _n(tmp_path: Path, provedor: str) -> Any:
    trocados: list[Any] = []
    return SimpleNamespace(
        cfg=carregar(tmp_path / "nao-existe.toml"),
        modelos_escolhidos=tmp_path / "m.json",
        provedor=provedor,
        extras=None,
        ponte=SimpleNamespace(trocar=trocados.append),
        _com_via_rapida=lambda c: c,
        _testar_modelo=lambda m: None,
        trocados=trocados,
    )


def test_muda_o_modelo_e_troca_o_cerebro_na_hora(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalogo, "com_reserva", lambda *a, **k: "cérebro novo")
    n = _n(tmp_path, "claude")
    assert Nucleo.mudar_modelo_do_cerebro(n, "claude", "claude-opus-5-5") == (
        "Modelo do cérebro: Opus 5.5."
    )
    assert n.trocados == ["cérebro novo"] and n.cfg["cerebro"]["modelo"] == "claude-opus-5-5"
    assert catalogo.ler_modelos(n.modelos_escolhidos) == {"claude": "claude-opus-5-5"}


def test_recusa_modelo_fora_da_lista_e_agente_desconhecido(tmp_path: Path) -> None:
    n = _n(tmp_path, "claude")
    with pytest.raises(ValueError, match="indisponível"):
        Nucleo.mudar_modelo_do_cerebro(n, "claude", "gpt-qualquer")
    with pytest.raises(ValueError, match="desconhecido"):
        Nucleo.mudar_modelo_do_cerebro(n, "gemini", "x")


def test_modelo_sem_acesso_e_recusado_sem_trocar(tmp_path: Path) -> None:
    n = _n(tmp_path, "claude")
    n._testar_modelo = lambda m: "Este modelo exige créditos de uso nesta conta."
    with pytest.raises(ValueError, match="créditos"):
        Nucleo.mudar_modelo_do_cerebro(n, "claude", "claude-fable-5-1")
    assert n.trocados == [] and catalogo.ler_modelos(n.modelos_escolhidos) == {}
