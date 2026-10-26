"""Silencioso trava o microfone (13/10/2026): nem "Ei Zé", nem botão, nem ao vivo; o app de voz
conectado é a exceção (26/10/2026)."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.avisos import modo
from zervis.nucleo import estados as e
from zervis.nucleo.laco import Nucleo


class _Nucleo(SimpleNamespace):
    microfone_travado = Nucleo.microfone_travado


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
    n = _Nucleo(
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


def test_silencioso_com_o_app_conectado_continua_ouvindo_e_falando(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    n = _n(tmp_path, monkeypatch)
    n._fonte = SimpleNamespace(do_app=True)  # o app de voz do celular
    n.maquina.estado = e.Estado.ATIVO
    Nucleo.mudar_modo_fala(n, "silencioso")
    assert n.captura.aberta and not n.voz.muda and n.postos == []
    n._fonte = SimpleNamespace(do_app=False)  # o navegador: o Silencioso vale
    assert n.microfone_travado
