"""Silencioso trava o microfone (13/10/2026): nem "Ei Zé", nem botão, nem ao vivo."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.avisos import modo
from zervis.nucleo import estados as e
from zervis.nucleo.laco import Nucleo


class _Captura:
    def __init__(self) -> None:
        self.aberta = True

    def abrir(self) -> None:
        self.aberta = True

    def fechar(self) -> None:
        self.aberta = False


def _n(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(modo, "gravar", lambda m: m)  # nada no disco
    eventos: list[Any] = []
    n = SimpleNamespace(
        modo_fala="avisos",
        voz=SimpleNamespace(muda=False, parar=lambda: None),
        captura=_Captura(),
        segmentador=SimpleNamespace(limpar=lambda: None),
        maquina=SimpleNamespace(estado=e.Estado.OUVINDO),
        eventos=SimpleNamespace(put=eventos.append),
        _ligar_ativacao=lambda: None,
        postos=eventos,
    )
    return n


def test_silencioso_fecha_o_microfone_e_os_outros_abrem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    n = _n(tmp_path, monkeypatch)
    Nucleo.mudar_modo_fala(n, "silencioso")
    assert not n.captura.aberta and n.postos == [e.Silencio()]  # parou de ouvir na hora
    n.maquina.estado = e.Estado.ATIVO
    Nucleo.mudar_modo_fala(n, "avisos")
    assert n.captura.aberta


def test_botao_recusa_no_silencioso() -> None:
    n = SimpleNamespace(modo_fala="silencioso", eventos=SimpleNamespace(put=lambda _: None))
    n.microfone_travado = True
    with pytest.raises(ValueError, match="Silencioso"):
        Nucleo.apertar(n)  # type: ignore[arg-type]
    assert Nucleo.microfone_travado.fget(SimpleNamespace(modo_fala="silencioso"))  # type: ignore[attr-defined]
    assert not Nucleo.microfone_travado.fget(SimpleNamespace(modo_fala="avisos"))  # type: ignore[attr-defined]
