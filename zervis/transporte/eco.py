"""Cancelamento de eco da voz remota: o app do celular e o navegador (ADR 0051).

Com o Zé numa caixa de som (ou no alto-falante do celular), a fala dele volta pelo microfone e ele
ouve a si mesmo. O cancelador de eco do Android não ajuda aí: só funciona com o áudio no modo de
ligação, e a caixa Bluetooth não entra nesse modo. Aqui o Zé sabe exatamente o que falou, então o
eco sai no servidor: o cancelador do WebRTC (AEC3, o do Google Meet, que já vem no SDK do LiveKit)
recebe a fala como referência e a tira do microfone, com supressão de ruído e filtro de graves.

O tempo é o da fala no aparelho: cada pedaço é marcado para quando deve tocar, e cada quadro do
microfone puxa a referência do seu instante. O que sobra de atraso (a saída do celular, o
Bluetooth, a rede na volta) o AEC3 acha sozinho até uns 400 ms; acima disso, uma medida do atraso
(correlação cruzada com fase, GCC-PHAT, nos últimos 3 s) atrasa a referência antes de entregá-la
(teste de bancada, 30/10/2026: uns 20 dB de eco a menos; a pessoa falando por cima continua
inteira).
"""

import collections
import logging
import threading

import numpy as np

log = logging.getLogger(__name__)

TAXA = 16000
BLOCO = 160  # 10 ms, o passo do AEC3
GUARDA_S = 4.0  # quanto de referência fica guardado para trás
SALTO_S = 0.25  # o relógio do microfone volta à chegada quando se afasta mais que isto
FOLGA_AEC_S = 0.15  # do atraso medido, o tanto que fica para o AEC3 achar sozinho
ATRASO_LIVRE_S = 0.35  # até aqui, o AEC3 dá conta sem ajuda
MEDIDA = 300  # 3 s (em blocos de 10 ms) para medir o atraso
MAIOR_ATRASO_S = 1.0
TAXA_MEDIDA = 8000  # a medida usa metade das amostras: sobra precisão de sobra


def _modulo(ruido: bool) -> object | None:
    try:
        from livekit import rtc  # só quem usa voz remota carrega o WebRTC

        return rtc.AudioProcessingModule(
            echo_cancellation=True, noise_suppression=ruido, high_pass_filter=True
        )
    except Exception:  # sem o WebRTC, a voz segue como antes
        log.warning("eco: cancelador indisponível; a voz remota segue sem ele", exc_info=True)
        return None


def _metade(x: np.ndarray) -> np.ndarray:
    """De 16 kHz para 8 kHz (a média de cada par), para a medida do atraso."""
    metade: np.ndarray = x.astype(np.float32).reshape(-1, 2).mean(axis=1)
    return metade


class Eco:
    """O cancelador de uma conexão de voz. `referencia` recebe a fala (thread da fala),
    `limpar` cada quadro do microfone (thread da conexão)."""

    def __init__(self, ruido: bool = True, modulo: object | None = None) -> None:
        self._apm = modulo if modulo is not None else _modulo(ruido)
        self._trava = threading.Lock()
        self._ref: collections.deque[tuple[float, np.ndarray]] = collections.deque()
        self._t_mic: float | None = None
        self.atraso_s = 0.0  # o que a referência é atrasada antes do AEC3 (só acima de 350 ms)
        self._hist_mic: collections.deque[np.ndarray] = collections.deque(maxlen=MEDIDA)
        self._hist_ref: collections.deque[np.ndarray] = collections.deque(maxlen=MEDIDA)
        self._blocos = 0
        self._candidato: float | None = None

    @property
    def ativo(self) -> bool:
        return self._apm is not None

    def referencia(self, pcm: bytes, toca_em: float) -> None:
        """A fala mandada ao aparelho (PCM de 16 bits a 16 kHz) e quando ela começa a tocar lá."""
        if self._apm is None or not pcm:
            return
        amostras = np.frombuffer(pcm[: len(pcm) // 2 * 2], "<i2").copy()
        with self._trava:
            self._ref.append((toca_em, amostras))
            while self._ref and self._ref[0][0] + len(self._ref[0][1]) / TAXA < toca_em - GUARDA_S:
                self._ref.popleft()

    def cortar(self, quando: float) -> None:
        """A fala foi interrompida: o aparelho jogou fora o que ainda não tinha tocado."""
        with self._trava:
            mantidos = collections.deque[tuple[float, np.ndarray]]()
            for inicio, amostras in self._ref:
                if inicio < quando:
                    mantidos.append((inicio, amostras[: max(0, int((quando - inicio) * TAXA))]))
            self._ref = mantidos

    def _janela(self, t: float, n: int) -> np.ndarray:
        saida = np.zeros(n, np.int16)
        for inicio, amostras in self._ref:
            de = round((t - inicio) * TAXA)
            if de >= len(amostras) or de + n <= 0:
                continue
            a, b = max(0, de), min(len(amostras), de + n)
            saida[a - de : b - de] = amostras[a:b]
        return saida

    def limpar(self, quadro: bytes, chegada: float) -> bytes:
        """Um quadro do microfone (PCM de 16 bits a 16 kHz) que acabou de chegar, sem o eco."""
        if self._apm is None or len(quadro) < BLOCO * 2:
            return quadro
        from livekit import rtc

        mic = np.frombuffer(quadro[: len(quadro) // 2 * 2], "<i2")
        duracao = len(mic) / TAXA
        # O relógio do microfone anda com as amostras; só volta à hora da chegada num salto (o
        # 4G entrega em rajadas: a chegada sozinha tremeria o atraso que o AEC3 aprendeu).
        if self._t_mic is None or abs(self._t_mic - (chegada - duracao)) > SALTO_S:
            self._t_mic = chegada - duracao
        t0 = self._t_mic
        self._t_mic += duracao
        saida = mic.copy()
        for i in range(0, len(mic) - BLOCO + 1, BLOCO):
            t = t0 + i / TAXA
            with self._trava:
                ref = self._janela(t - self.atraso_s, BLOCO)
                crua = self._janela(t, BLOCO) if self.atraso_s else ref
            reverso = rtc.AudioFrame.create(TAXA, 1, BLOCO)
            np.frombuffer(reverso.data, np.int16)[:] = ref
            self._apm.process_reverse_stream(reverso)  # type: ignore[attr-defined]
            proprio = rtc.AudioFrame.create(TAXA, 1, BLOCO)
            np.frombuffer(proprio.data, np.int16)[:] = mic[i : i + BLOCO]
            self._apm.process_stream(proprio)  # type: ignore[attr-defined]
            saida[i : i + BLOCO] = np.frombuffer(proprio.data, np.int16)
            self._medir(mic[i : i + BLOCO], crua)
        return saida.tobytes()

    def _medir(self, mic: np.ndarray, ref: np.ndarray) -> None:
        self._hist_mic.append(_metade(mic))
        self._hist_ref.append(_metade(ref))
        self._blocos += 1
        if self._blocos % 100 == 0 and len(self._hist_ref) == MEDIDA:
            self._estimar()

    def _estimar(self) -> None:
        """O atraso entre a fala e o eco dela nos últimos 3 s (GCC-PHAT); o atraso aplicado só muda
        com duas medidas seguidas que concordam e um pico claro."""
        r = np.concatenate(self._hist_ref)
        m = np.concatenate(self._hist_mic)
        if (np.abs(r) > 300).mean() < 0.1:  # pouca fala na janela: nada a medir
            return
        n = 1 << (len(r) * 2 - 1).bit_length()
        cruzado = np.conj(np.fft.rfft(r, n)) * np.fft.rfft(m, n)
        correlacao = np.fft.irfft(cruzado / (np.abs(cruzado) + 1e-9), n)
        janela = correlacao[: int(MAIOR_ATRASO_S * TAXA_MEDIDA)]
        melhor = int(np.argmax(janela))
        pico, fundo = float(janela[melhor]), float(np.median(np.abs(janela))) + 1e-9
        # sem um pico claro, ou colado no limite da busca (a borda da janela), não é o eco
        if pico / fundo < 8 or melhor >= len(janela) * 0.95:
            return
        medido = melhor / TAXA_MEDIDA
        novo = 0.0 if medido <= ATRASO_LIVRE_S else medido - FOLGA_AEC_S
        concorda = self._candidato is not None and abs(self._candidato - novo) < 0.03
        if concorda and abs(novo - self.atraso_s) > 0.06:
            log.info("eco: atraso da saída %.0f ms", medido * 1000)
            self.atraso_s = novo
        self._candidato = novo
