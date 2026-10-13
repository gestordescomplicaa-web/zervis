"""Chamado sem ninguém falar depois (13/10/2026: vídeos no navegador acionavam o Zé, que ficava
20 s ouvindo e mandando áudio ao reconhecimento): a escuta fecha em poucos segundos."""

import time
from types import SimpleNamespace

from jarvis.nucleo.laco import PRIMEIRA_FALA_S, Nucleo


def _n(ouviu: bool, ha: float, segurando: bool = False, ao_vivo: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        _ouviu_voz=ouviu,
        _ouvindo_desde=time.monotonic() - ha,
        maquina=SimpleNamespace(segurando=segurando, ao_vivo=ao_vivo),
    )


def test_fecha_se_ninguem_falou_depois_do_chamado() -> None:
    assert Nucleo._ninguem_falou(_n(False, PRIMEIRA_FALA_S + 1))  # type: ignore[arg-type]
    assert not Nucleo._ninguem_falou(_n(False, 2))  # type: ignore[arg-type]  # ainda dá tempo
    assert not Nucleo._ninguem_falou(_n(True, 30))  # type: ignore[arg-type]  # falou: o prazo normal


def test_botao_e_ao_vivo_nao_fecham_por_isso() -> None:
    assert not Nucleo._ninguem_falou(_n(False, 30, segurando=True))  # type: ignore[arg-type]
    assert not Nucleo._ninguem_falou(_n(False, 30, ao_vivo=True))  # type: ignore[arg-type]
