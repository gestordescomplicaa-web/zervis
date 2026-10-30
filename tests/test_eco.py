"""O cancelador de eco da voz remota (ADR 0051): a fala do Zé que volta pelo microfone sai."""

import numpy as np
import pytest

from zervis.transporte import eco as modulo
from zervis.transporte.eco import TAXA, Eco
from zervis.transporte.navegador import BYTES_QUADRO, TocadorNavegador, VozNavegador

QUADRO_S = BYTES_QUADRO / 2 / TAXA


def _fala(segundos: float, semente: int) -> np.ndarray:
    """Um sinal com cara de fala: ruído em rajadas de sílaba, nas frequências da voz."""
    rng = np.random.default_rng(semente)
    n = int(segundos * TAXA)
    ruido = np.convolve(rng.standard_normal(n), np.hanning(9), "same")
    silabas = (np.sin(np.arange(n) / TAXA * 2 * np.pi * 4) > -0.2).astype(np.float32)
    return (ruido * silabas * 0.25).astype(np.float32)


def _eco_de(fala: np.ndarray, atraso_s: float) -> np.ndarray:
    sala = np.zeros(1200, np.float32)
    sala[0], sala[400], sala[900] = 0.6, 0.25, 0.1  # a caixa e duas paredes
    eco = np.convolve(fala, sala)[: len(fala)]
    d = int(atraso_s * TAXA)
    return np.concatenate([np.zeros(d, np.float32), eco])[: len(fala)]


def _passar(e: Eco, mic: np.ndarray, t0: float) -> np.ndarray:
    saida = []
    n = BYTES_QUADRO // 2
    for k in range(0, len(mic) - n + 1, n):
        quadro = (np.clip(mic[k : k + n], -1, 1) * 32767).astype("<i2").tobytes()
        saida.append(np.frombuffer(e.limpar(quadro, t0 + (k + n) / TAXA), "<i2") / 32768)
    return np.concatenate(saida)


def _db(x: np.ndarray) -> float:
    return float(10 * np.log10(np.mean(x.astype(np.float64) ** 2) + 1e-12))


def _cenario(atraso_s: float) -> tuple[Eco, np.ndarray, np.ndarray]:
    fala = _fala(8.0, 1)
    e = Eco()
    assert e.ativo
    e.referencia((fala * 32767).astype("<i2").tobytes(), 100.0)
    mic = _eco_de(fala, atraso_s)
    return e, mic, _passar(e, mic, 100.0)


def test_a_fala_do_ze_some_do_microfone() -> None:
    _, mic, saida = _cenario(0.25)  # caixa Bluetooth e rede: um quarto de segundo
    depois = slice(3 * TAXA, len(saida))  # o AEC3 aprende nos primeiros segundos
    assert _db(mic[depois]) - _db(saida[depois]) > 15


def test_o_atraso_longo_da_caixa_e_medido_e_compensado() -> None:
    e, mic, saida = _cenario(0.7)
    assert 0.5 < e.atraso_s < 0.6  # 700 ms medidos, 150 ms deixados para o AEC3
    depois = slice(5 * TAXA, len(saida))
    assert _db(mic[depois]) - _db(saida[depois]) > 15


def test_quem_fala_por_cima_continua_ouvido() -> None:
    fala, pessoa = _fala(8.0, 1), _fala(3.0, 7)
    e = Eco()
    e.referencia((fala * 32767).astype("<i2").tobytes(), 100.0)
    mic = _eco_de(fala, 0.25)
    mic[5 * TAXA : 8 * TAXA] += pessoa
    saida = _passar(e, mic, 100.0)
    so_eco = slice(3 * TAXA, 5 * TAXA)
    por_cima = slice(5 * TAXA, len(saida))
    assert _db(saida[por_cima]) - _db(saida[so_eco]) > 10  # a pessoa fica bem acima do resto


def test_interromper_descarta_a_fala_que_nao_tocou() -> None:
    e = Eco()
    e.referencia(np.ones(TAXA * 2, "<i2").tobytes(), 10.0)
    e.cortar(10.5)
    assert e._janela(10.4, 160).all() and not e._janela(10.6, 160).any()


def test_sem_o_webrtc_a_voz_passa_como_antes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo, "_modulo", lambda ruido: None)
    e = Eco()
    quadro = np.arange(1280, dtype="<i2").tobytes()
    assert not e.ativo and e.limpar(quadro, 1.0) == quadro


class _Conexao:
    aberta = True

    def __init__(self) -> None:
        self.textos: list[str] = []

    def texto(self, m: str) -> None:
        self.textos.append(m)

    def binario(self, _: bytes) -> None:
        pass


def test_a_fala_mandada_ao_aparelho_vira_referencia_e_parar_corta() -> None:
    voz = VozNavegador(_Conexao())  # type: ignore[arg-type]
    tocador = TocadorNavegador(voz, 22050)
    tocador.write(np.full(22050 // 10, 0.5, "<f4").tobytes())  # 100 ms de fala
    _, amostras = voz.eco._ref[0]
    assert len(amostras) == TAXA // 10 and abs(amostras.mean() - 0.5 * 32767) < 2
    tocador.kill()  # o aparelho joga fora o que não tocou: quase nada tinha dado tempo de tocar
    assert sum(len(a) for _, a in voz.eco._ref) < TAXA // 20
