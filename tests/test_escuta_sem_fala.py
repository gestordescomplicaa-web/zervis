"""Chamado sem ninguém falar depois (13/10/2026: vídeos no navegador acionavam o Zé, que ficava
20 s ouvindo e mandando áudio ao reconhecimento): a escuta fecha em poucos segundos."""

import time
from pathlib import Path
from types import SimpleNamespace

from zervis.nucleo.laco import PRIMEIRA_FALA_S, Nucleo


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


def test_chamado_baixo_demais_e_ignorado() -> None:
    """13/10/2026: o detector disparou em silêncio digital (-91 dBFS) e em voz de fundo
    (-53 a -87 dBFS); a pessoa chamando ao microfone ficou entre -22 e -28 dBFS."""
    import numpy as np

    from zervis.nucleo.laco import nivel_de_pico

    t = np.arange(16000) / 16000
    alto = (0.05 * 32767 * np.sin(2 * np.pi * 300 * t)).astype("<i2").tobytes()  # ~ -29 dBFS
    fundo = (0.001 * 32767 * np.sin(2 * np.pi * 300 * t)).astype("<i2").tobytes()  # ~ -63 dBFS
    assert nivel_de_pico(alto) > -40 > nivel_de_pico(fundo)
    assert nivel_de_pico(bytes(32000)) < -100  # silêncio
    assert nivel_de_pico(b"") == -120.0


def test_reconhecimento_prefere_o_nome_do_ze() -> None:
    from urllib.parse import parse_qs

    from zervis.voz import deepgram

    termos = parse_qs(deepgram.consulta())["keyterm"]
    assert {"Zé", "Ei Zé", "Hey Zé"} <= set(termos)


def test_o_chamado_universal_vem_no_repositorio(tmp_path: Path) -> None:
    """Quem instala do zero tem o "Ei Zé" sem gravar a própria voz (13/10/2026)."""
    from zervis.config import carregar
    from zervis.voz.ativacao import ModeloAtivacao, carregar_modelo

    caminho = carregar(tmp_path / "nao-existe.toml").caminho("ativacao", "modelo")
    assert "/voz/modelos/ei_ze.npz" in str(caminho)
    modelo = carregar_modelo(caminho)
    assert isinstance(modelo, ModeloAtivacao) and 0.5 <= modelo.limiar < 1
