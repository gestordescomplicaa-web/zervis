"""O chamado que é a própria voz do Zé voltando pelo microfone não o interrompe (17/11/2026)."""

import time
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tests.test_latencia_nucleo import NucleoCronometrado
from zervis.nucleo import estados as e
from zervis.voz import eco
from zervis.voz.eco import Referencia

TAXA = 16000


def fala(semente: int, segundos: float) -> np.ndarray:
    """Algo com o desenho da fala: sílabas de 120 a 300 ms com pausas, cada uma com o seu tom
    e os seus harmônicos, em -1 a 1."""
    sorteio = np.random.default_rng(semente)
    saida = np.zeros(int(segundos * TAXA), dtype=np.float32)
    i = 0
    while i < len(saida):
        n = int(sorteio.uniform(0.12, 0.30) * TAXA)
        tempo = np.arange(n) / TAXA
        tom = sorteio.uniform(100, 260)
        silaba = sum(
            sorteio.uniform(0.1, 1.0) / k * np.sin(2 * np.pi * tom * k * tempo) for k in range(1, 9)
        )
        silaba = silaba * np.hanning(n) * sorteio.uniform(0.3, 1.0)
        fim = min(len(saida), i + n)
        saida[i:fim] = silaba[: fim - i] * 0.12
        i = fim + int(sorteio.uniform(0.03, 0.15) * TAXA)
    return saida


def no_microfone(som: np.ndarray, atraso_s: float = 0.14, ganho: float = 0.1) -> np.ndarray:
    """O caminho do fone ao microfone: mais baixo, um pouco abafado, atrasado e com chiado."""
    abafado = np.convolve(som, np.ones(4) / 4, mode="same") * ganho
    atrasado = np.concatenate([np.zeros(int(atraso_s * TAXA)), abafado])[: len(som)]
    chiado = np.random.default_rng(9).normal(0, 0.0005, len(som))
    return np.asarray(atrasado + chiado, dtype=np.float64)


def pcm(x: np.ndarray) -> bytes:
    return np.asarray(np.clip(x * 32768, -32768, 32767), dtype="<i2").tobytes()


def _avaliar(microfone: np.ndarray, tocado: np.ndarray, fim: float = 10.0) -> eco.Veredito | None:
    """`tocado` começou a soar em 5 s; o microfone termina em `fim`."""
    ref = Referencia(relogio=lambda: fim)
    for k in range(0, len(tocado), 4096):  # entregue aos pedaços, como o reprodutor recebe
        ref.tocou(5.0 + k / TAXA, tocado[k : k + 4096], TAXA)
    return ref.avaliar(pcm(microfone), fim)


def test_a_propria_fala_no_microfone_e_eco() -> None:
    tocado = fala(1, 6.0)
    ouvido = no_microfone(tocado)
    microfone = ouvido[int(2.0 * TAXA) : int(5.0 * TAXA)]  # 3 s, terminando em 10 s
    veredito = _avaliar(microfone, tocado)
    assert veredito is not None and veredito.eco, veredito


@pytest.mark.parametrize("volume", [0.5, 1.0])
def test_alguem_chamando_por_cima_da_fala_nao_e_eco(volume: float) -> None:
    """A voz nova não está no que o Zé tocou: sobra bem mais do que o eco explica."""
    tocado = fala(1, 6.0)
    microfone = no_microfone(tocado)[int(2.0 * TAXA) : int(5.0 * TAXA)].copy()
    chamado = fala(2, 0.9) * 0.4 * volume  # "Ei Zé" no fim, mais alto que o vazamento
    microfone[-len(chamado) :] += chamado
    veredito = _avaliar(microfone, tocado)
    assert veredito is not None and not veredito.eco, veredito


def test_sem_nada_tocado_nao_ha_o_que_comparar() -> None:
    ref = Referencia(relogio=lambda: 10.0)
    assert ref.avaliar(pcm(fala(3, 3.0)), 10.0) is None
    ref.tocou(1.0, fala(1, 1.0), TAXA)  # tocou, mas muito antes do chamado
    assert ref.avaliar(pcm(fala(3, 3.0)), 10.0) is None


def test_a_referencia_esquece_o_que_tocou_ha_muito_tempo() -> None:
    agora = [0.0]
    ref = Referencia(relogio=lambda: agora[0])
    ref.tocou(0.0, fala(1, 1.0), TAXA)
    agora[0] = 20.0
    ref.tocou(20.0, fala(1, 1.0), TAXA)
    assert len(ref._trechos) == 1


def test_outra_taxa_e_convertida() -> None:
    ref = Referencia(relogio=lambda: 2.0)
    ref.tocou(0.0, np.ones(22050, dtype=np.float32), 22050)
    trecho = ref.trecho(0.0, 1.0)
    assert trecho is not None and len(trecho) == TAXA and trecho.min() == pytest.approx(1.0)


@pytest.fixture
def nucleo(tmp_path: Path) -> Iterator[NucleoCronometrado]:
    n = NucleoCronometrado(tmp_path)
    try:
        yield n
    finally:
        n.transcricoes.shutdown(wait=True)
        n._fechar_latencia("servico_parado")
        n.latencias.fechar()


def _chamar_durante_a_fala(nucleo: NucleoCronometrado, microfone: np.ndarray) -> list[bool]:
    """O detector dispara no último quadro de 3 s de microfone, com o Zé falando."""
    n = nucleo
    guardados: list[bool] = []
    n._guardar_chamado = lambda ignorado=False: guardados.append(ignorado)  # type: ignore[method-assign]
    n._fonte = None
    n.cfg = {"escuta": n.cfg["escuta"], "ativacao": {"nivel_minimo_dbfs": -90.0}}  # type: ignore[assignment]
    quadros = [microfone[k : k + 1280] for k in range(0, len(microfone), 1280)]
    disparos = iter([False] * (len(quadros) - 1) + [True])
    n.detector = SimpleNamespace(  # type: ignore[assignment]
        processar=lambda a: next(disparos), reiniciar=lambda: None, nota_disparo=0.8
    )
    n.maquina.estado = e.Estado.FALANDO
    agora = time.monotonic()
    tocado = fala(1, 8.0)
    n.voz.eco.tocou(agora - 5.0, tocado, TAXA)
    eco_inteiro = no_microfone(tocado)
    fim = int(5.0 * TAXA)
    n._antes_do_chamado.clear()
    trecho = eco_inteiro[fim - len(microfone) : fim] + microfone
    for k in range(0, len(trecho), 1280):
        n._quadro(pcm(trecho[k : k + 1280]))
    return guardados


def test_o_eco_da_propria_fala_nao_interrompe_o_ze(
    nucleo: NucleoCronometrado, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("zervis.nucleo.ouvir.nivel_chamado.PADRAO.minimo", lambda piso: piso)
    monkeypatch.setattr("zervis.nucleo.ouvir.nivel_chamado.PADRAO.ativou", lambda nivel: None)
    guardados = _chamar_durante_a_fala(nucleo, np.zeros(38 * 1280))
    assert guardados == [True]  # guardado como ignorado, para conferir depois
    assert nucleo.maquina.estado is e.Estado.FALANDO  # segue falando


def test_o_chamado_de_verdade_por_cima_da_fala_interrompe(
    nucleo: NucleoCronometrado, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("zervis.nucleo.ouvir.nivel_chamado.PADRAO.minimo", lambda piso: piso)
    monkeypatch.setattr("zervis.nucleo.ouvir.nivel_chamado.PADRAO.ativou", lambda nivel: None)
    chamado = np.zeros(38 * 1280)
    voz = fala(2, 0.9) * 0.4
    chamado[-len(voz) :] = voz
    guardados = _chamar_durante_a_fala(nucleo, chamado)
    assert guardados == [False]
    assert nucleo.maquina.estado is e.Estado.OUVINDO
