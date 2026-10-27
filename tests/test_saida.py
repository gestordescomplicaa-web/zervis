"""Saída de voz: pedaços por frase, streaming até o reprodutor e interrupção."""

import io
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np

from zervis.voz.saida import Voz, pedacos


def test_pedacos_respeitam_frases_e_limite() -> None:
    partes = pedacos("Primeira frase. " * 100, limite=100)
    assert all(len(p) <= 100 for p in partes)
    assert all(p.endswith(".") for p in partes)
    assert pedacos("Curta.") == ["Curta."]
    assert all(len(p) <= 50 for p in pedacos("a" * 30 + " " + "b" * 30, limite=50))


def test_primeira_frase_vai_sozinha() -> None:
    assert pedacos("Pronto. Agora o resto da resposta.")[0] == "Pronto."


class RespostaFalsa(io.BytesIO):
    def read1(self, n: int | None = -1) -> bytes:
        return self.read(min(n or 1000, 1000))  # chega aos poucos, cortando no meio das amostras


def _esperar(condicao: object, limite: float = 3.0) -> None:
    fim = time.monotonic() + limite
    while time.monotonic() < fim and not condicao():  # type: ignore[operator]
        time.sleep(0.01)


def test_pcm_do_cadu_chega_inteiro_ao_reprodutor(tmp_path: Path) -> None:
    saida = tmp_path / "tocado.raw"
    pcm = np.linspace(-0.5, 0.5, 24000, dtype="<f4")
    respostas: list[RespostaFalsa] = []

    def fluxo(texto: str) -> tuple[int, RespostaFalsa]:
        respostas.append(RespostaFalsa(pcm.tobytes()))
        return 24000, respostas[-1]

    ociosa = threading.Event()
    voz = Voz(
        abrir_fluxo=fluxo,
        folga_s=0.25,
        reprodutor=lambda taxa: ["/bin/sh", "-c", f"cat > '{saida}'"],
    )
    voz.ao_ficar_ociosa = lambda numero: ociosa.set()
    voz.falar("Olá.")
    assert ociosa.wait(5)
    assert (voz.faladas, voz.ultimo_erro) == (1, None)
    np.testing.assert_array_equal(np.frombuffer(saida.read_bytes(), "<f4"), pcm)
    assert respostas[0].closed
    assert voz.primeira_fala_s is not None


def test_parar_corta_a_fala_e_descarta_a_fila() -> None:
    comecou = threading.Event()

    def fluxo_lento(texto: str) -> tuple[int, RespostaFalsa]:
        comecou.set()
        return 24000, RespostaFalsa(np.zeros(24000 * 30, "<f4").tobytes())

    voz = Voz(abrir_fluxo=fluxo_lento, reprodutor=lambda taxa: ["/bin/sh", "-c", "cat > /dev/null"])
    voz.falar("Uma resposta muito longa.")
    voz.falar("Outra que nem deve começar.")
    assert comecou.wait(3)
    inicio = time.monotonic()
    voz.parar()
    _esperar(lambda: not voz.ocupada)
    assert not voz.ocupada
    assert time.monotonic() - inicio < 1.0
    assert voz.faladas == 0


def test_fluxo_do_piper_entrega_frase_a_frase_e_para_ao_fechar() -> None:
    from zervis.voz.piper import FluxoGerado

    geradas: list[int] = []

    def frases() -> Iterator[bytes]:
        for i in range(3):
            geradas.append(i)
            yield np.full(2, i, "<f4").tobytes()

    fluxo = FluxoGerado(frases())
    assert np.frombuffer(fluxo.read1(), "<f4").tolist() == [0.0, 0.0]
    assert geradas == [0]  # a segunda frase só é sintetizada quando pedida
    fluxo.close()
    assert fluxo.read1() == b"" and geradas == [0]


def test_primeiro_som_e_medido_antes_de_bloquear_no_resto_do_pcm(tmp_path: Path) -> None:
    """O reprodutor só libera o pipe depois que o observador avisar: detecta o marco tardio."""
    aviso = tmp_path / "iniciou"
    tocado = tmp_path / "pcm"
    script = (
        "import sys,time,pathlib; primeira=sys.stdin.buffer.read(4); "
        "prazo=time.monotonic()+3\n"
        "while not pathlib.Path(sys.argv[1]).exists() and time.monotonic()<prazo: "
        "time.sleep(.01)\n"
        "pathlib.Path(sys.argv[2]).write_bytes(primeira+sys.stdin.buffer.read())"
    )
    pcm = np.zeros(24000, "<f4").tobytes()
    ociosa = threading.Event()
    tempos: list[float] = []

    def iniciou(em: float) -> None:
        tempos.append(em)
        aviso.touch()

    voz = Voz(
        abrir_fluxo=lambda t: (24000, RespostaFalsa(pcm)),
        reprodutor=lambda t: [sys.executable, "-c", script, str(aviso), str(tocado)],
    )
    voz.ao_ficar_ociosa = lambda n: ociosa.set()
    inicio = time.monotonic()
    voz.falar("Pronto. Outra frase.", ao_iniciar=iniciou)
    assert ociosa.wait(5)
    assert len(tempos) == 1 and inicio <= tempos[0] < inicio + 2
    assert tocado.read_bytes() == pcm and voz.ultimo_erro is None


def test_sem_pcm_nao_avisa_som_e_observador_quebrado_nao_corta_voz() -> None:
    def quebrado(em: float) -> None:
        raise RuntimeError("não pode impedir a fala")

    tempos: list[float] = []
    for pcm, callback in [(b"", tempos.append), (np.zeros(1000, "<f4").tobytes(), quebrado)]:
        cb: Callable[[float], None] = callback
        ociosa = threading.Event()

        def fluxo(texto: str, dados: bytes = pcm) -> tuple[int, RespostaFalsa]:
            return 24000, RespostaFalsa(dados)

        voz = Voz(abrir_fluxo=fluxo, reprodutor=lambda t: ["/bin/cat"])
        voz.ao_ficar_ociosa = lambda n, ociosa=ociosa: ociosa.set()
        voz.falar("Oi.", ao_iniciar=cb)
        assert ociosa.wait(3) and voz.ultimo_erro is None
    assert tempos == []


def test_trabalho_cancelado_nao_avisa_primeiro_som() -> None:
    entrou, liberar, ociosa = threading.Event(), threading.Event(), threading.Event()
    tempos: list[float] = []

    def fluxo(texto: str) -> tuple[int, RespostaFalsa]:
        entrou.set()
        assert liberar.wait(3)
        return 24000, RespostaFalsa(np.zeros(1000, "<f4").tobytes())

    voz = Voz(abrir_fluxo=fluxo, reprodutor=lambda t: ["/bin/cat"])
    voz.ao_ficar_ociosa = lambda n: ociosa.set()
    voz.falar("Oi.", ao_iniciar=tempos.append)
    assert entrou.wait(3)
    voz.parar()
    liberar.set()
    assert ociosa.wait(3)
    assert tempos == [] and voz.faladas == 0


def test_muda_nao_toca_e_avisa_que_ficou_ociosa() -> None:
    abertos: list[str] = []

    def fluxo(texto: str) -> tuple[int, RespostaFalsa]:
        abertos.append(texto)
        return 24000, RespostaFalsa(b"")

    ociosa = threading.Event()
    voz = Voz(abrir_fluxo=fluxo, reprodutor=lambda t: ["/bin/cat"])
    voz.muda = True
    voz.ao_ficar_ociosa = lambda numero: ociosa.set()
    voz.falar("Modo silencioso.")
    assert ociosa.wait(2)
    assert abertos == []
