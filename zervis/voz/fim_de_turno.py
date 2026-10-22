"""Fim de turno pela entonação: o Smart Turn v3.2 (Pipecat, BSD-2) diz se o usuário terminou.

Em vez de esperar sempre 2 s de silêncio, depois de uma pausa curta o modelo olha os últimos
8 s de áudio e devolve a probabilidade de a fala estar completa (português: 94,5% de acerto
no benchmark oficial). Na dúvida, o silêncio fixo continua valendo.

Pré-processamento igual ao `WhisperFeatureExtractor(chunk_length=8)` do transformers
(log-mel de 80 faixas, janela de 400, passo de 160, normalização média zero/variância um),
reimplementado em numpy para não trazer o transformers; a equivalência é medida por
provas/prova_fim_de_turno.py. Adaptado de github.com/pipecat-ai/smart-turn (inference.py,
audio_utils.py) e do transformers (Apache-2.0); ver THIRD_PARTY.md.
"""

from pathlib import Path

import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray

TAXA = 16000
SEGUNDOS = 8
N_FFT = 400
PASSO = 160
N_MEL = 80
Floats = NDArray[np.float64]


def _hz_para_mel(f: Floats) -> Floats:
    """Escala mel "slaney" (linear até 1 kHz, logarítmica acima), como no Whisper."""
    f_sp = 200.0 / 3
    mel = f / f_sp
    log_inicio = 1000.0 / f_sp
    passo_log = np.log(6.4) / 27.0
    acima = f >= 1000.0
    mel[acima] = log_inicio + np.log(f[acima] / 1000.0) / passo_log
    return mel


def _mel_para_hz(mel: Floats) -> Floats:
    f_sp = 200.0 / 3
    f = mel * f_sp
    log_inicio = 1000.0 / f_sp
    passo_log = np.log(6.4) / 27.0
    acima = mel >= log_inicio
    f[acima] = 1000.0 * np.exp(passo_log * (mel[acima] - log_inicio))
    return f


def filtros_mel() -> Floats:
    """Banco triangular (201 x 80) com normalização "slaney" (`mel_filter_bank` do transformers)."""
    freqs_fft = np.linspace(0, TAXA // 2, 1 + N_FFT // 2)
    mels = np.linspace(
        _hz_para_mel(np.array([0.0]))[0], _hz_para_mel(np.array([8000.0]))[0], N_MEL + 2
    )
    freqs_filtro = _mel_para_hz(mels)
    diferenca = np.diff(freqs_filtro)
    inclinacao = freqs_filtro[None, :] - freqs_fft[:, None]
    descida = -inclinacao[:, :-2] / diferenca[:-1]
    subida = inclinacao[:, 2:] / diferenca[1:]
    banco = np.maximum(0.0, np.minimum(descida, subida))
    banco *= 2.0 / (freqs_filtro[2 : N_MEL + 2] - freqs_filtro[:N_MEL])
    return banco


FILTROS = filtros_mel()
JANELA = np.hanning(N_FFT + 1)[:-1]  # Hann periódica


def ultimos_segundos(audio: NDArray[np.floating], segundos: int = SEGUNDOS) -> NDArray[np.floating]:
    """Os últimos `segundos` de áudio; se for mais curto, completa com zeros no começo."""
    total = segundos * TAXA
    if len(audio) >= total:
        return audio[-total:]
    return np.pad(audio, (total - len(audio), 0))


def features(audio: NDArray[np.floating]) -> NDArray[np.float32]:
    """Log-mel (1, 80, 800) de 8 s de áudio em float (-1..1)."""
    # Como no original: a onda chega em float32 e é normalizada em float32; o espectro, em
    # float64. Normalizar em float64 desviava a probabilidade em até 0,012 (modelo int8).
    x32 = ultimos_segundos(audio).astype(np.float32)
    x32 = (x32 - x32.mean()) / np.sqrt(x32.var() + 1e-7)
    x = np.pad(x32.astype(np.float64), N_FFT // 2, mode="reflect")
    quadros = 1 + (len(x) - N_FFT) // PASSO
    indices = np.arange(N_FFT)[None, :] + PASSO * np.arange(quadros)[:, None]
    espectro = np.abs(np.fft.rfft(x[indices] * JANELA, n=N_FFT)) ** 2
    log_mel = np.log10(np.maximum(espectro @ FILTROS, 1e-10)).T[:, :-1]
    log_mel = np.maximum(log_mel, log_mel.max() - 8.0)
    resultado: NDArray[np.float32] = ((log_mel + 4.0) / 4.0)[None].astype(np.float32)
    return resultado


class FimDeTurno:
    def __init__(self, modelo: Path) -> None:
        opcoes = ort.SessionOptions()
        opcoes.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        opcoes.inter_op_num_threads = 1
        opcoes.intra_op_num_threads = 1
        self.sessao = ort.InferenceSession(
            str(modelo), sess_options=opcoes, providers=["CPUExecutionProvider"]
        )

    def __call__(self, pcm: bytes) -> float:
        """Probabilidade de a fala em `pcm` (int16, 16 kHz) estar completa."""
        audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        saida = self.sessao.run(None, {"input_features": features(audio)})
        return float(saida[0][0].item())
