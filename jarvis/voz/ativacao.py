"""Detector do chamado pessoal ("Ei Zé"; antes "Hey Orca") e detector de voz (VAD), no onnxruntime.

Adaptado do openWakeWord 0.6.0 (David Scripka, Apache-2.0; ver THIRD_PARTY.md): o mesmo
pré-processamento em fluxo (`AudioFeatures._streaming_features` e `VAD`), só para quadros de
80 ms, sem o pacote — ele exige tflite-runtime, que não existe para Python recente, e traz
scikit-learn e scipy (0,7 s de importação) que o Zé não usa.

Diferença proposital: o original começa o buffer com embeddings de ruído aleatório; aqui ele
começa vazio e o detector só pontua depois de 16 quadros reais (1,28 s). Determinístico e sem
pontuação sobre ruído inventado.

O classificador é um MLP treinado com a voz do usuário: `ei_ze.npz`, por `treino_ativacao.py`
(antes o `hey_orca.npz` do Zé antigo, no mesmo formato).
"""

from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray

QUADRO = 1280  # amostras de 80 ms a 16 kHz
JANELA = 16  # embeddings pontuados juntos (16 x 80 ms = 1,28 s)
MEL_POR_EMBEDDING = 76
AUDIO_EXTRA = 160 * 3  # contexto que o modelo de mel pede além do quadro
MEL_MAX = 10 * 97  # ~10 s de espectrograma
FEATURES_MAX = 120  # ~10 s de embeddings

Audio = NDArray[np.int16]
Floats = NDArray[np.float32]


def _sessao(caminho: Path) -> ort.InferenceSession:
    opcoes = ort.SessionOptions()
    opcoes.inter_op_num_threads = 1
    opcoes.intra_op_num_threads = 1
    return ort.InferenceSession(
        str(caminho), sess_options=opcoes, providers=["CPUExecutionProvider"]
    )


class VAD:
    """Silero VAD do openWakeWord: probabilidade de fala de um quadro int16 a 16 kHz."""

    def __init__(self, modelo: Path) -> None:
        self.sessao = _sessao(modelo)
        self.taxa = np.array(16000, dtype=np.int64)
        self.reiniciar()

    def reiniciar(self) -> None:
        self._h = np.zeros((2, 1, 64), dtype=np.float32)
        self._c = np.zeros((2, 1, 64), dtype=np.float32)

    def prever(self, audio: Audio, tamanho: int = 640) -> float:
        notas = []
        for i in range(0, len(audio), tamanho):
            pedaco = (audio[i : i + tamanho] / 32767).astype(np.float32)
            entrada = {"input": pedaco[None,], "h": self._h, "c": self._c, "sr": self.taxa}
            saida, self._h, self._c = self.sessao.run(None, entrada)
            notas.append(float(saida[0][0]))
        return float(np.mean(notas)) if notas else 0.0


class SemVAD:
    """Sem o modelo do Silero (download que falhou): nenhum quadro conta como fala."""

    def reiniciar(self) -> None:
        pass

    def prever(self, audio: Audio, tamanho: int = 640) -> float:
        return 0.0


class Features:
    """Embeddings de fala (speech_embedding do Google) em fluxo, um quadro de 80 ms por vez."""

    def __init__(self, modelo_mel: Path, modelo_embedding: Path) -> None:
        self.mel = _sessao(modelo_mel)
        self.embedding = _sessao(modelo_embedding)
        self.reiniciar()

    def reiniciar(self) -> None:
        self.bruto: deque[int] = deque(maxlen=QUADRO + AUDIO_EXTRA)
        self.espectro: Floats = np.ones((MEL_POR_EMBEDDING, 32), dtype=np.float32)
        self.buffer: Floats = np.zeros((0, 96), dtype=np.float32)

    def _mel(self, audio: Floats) -> Floats:
        saida = self.mel.run(None, {"input": audio[None,]})
        # Mesma transformação do openWakeWord para aproximar a implementação do TensorFlow.
        resultado: Floats = np.squeeze(saida[0]) / 10 + 2
        return resultado

    def __call__(self, quadro: Audio) -> None:
        if len(quadro) != QUADRO:
            raise ValueError(f"quadro precisa de {QUADRO} amostras, veio {len(quadro)}")
        self.bruto.extend(quadro.tolist())
        audio = np.array(self.bruto, dtype=np.float32)
        self.espectro = np.vstack((self.espectro, self._mel(audio)))[-MEL_MAX:]
        janela = self.espectro[-MEL_POR_EMBEDDING:].astype(np.float32)[None, :, :, None]
        novo = self.embedding.run(None, {"input_1": janela})[0].squeeze()
        self.buffer = np.vstack((self.buffer, novo[None,]))[-FEATURES_MAX:]

    def ultimas(self, n: int = JANELA) -> Floats:
        resultado: Floats = self.buffer[-n:][None,].astype(np.float32)
        return resultado


class SemFeatures(Features):
    """Sem os modelos do openWakeWord: o buffer nunca enche, então o chamado nunca dispara."""

    def __init__(self) -> None:
        self.reiniciar()

    def __call__(self, quadro: Audio) -> None:
        pass


def faltando(*modelos: Path) -> list[str]:
    """Os arquivos de modelo que não estão na máquina (o download falhou ou nunca rodou)."""
    return [m.name for m in modelos if not m.is_file()]


class ModeloAtivacao:
    """MLP em numpy salvo pelo treino do Zé antigo (pesos W0.., b0.., média, desvio, limiar)."""

    def __init__(self, caminho: Path) -> None:
        pesos: Any = np.load(caminho)
        self.camadas = [(pesos[f"W{i}"], pesos[f"b{i}"]) for i in range(int(pesos["depth"]))]
        self.media, self.desvio = pesos["mean"], pesos["std"]
        self.limiar = float(pesos["threshold"])
        self.treinada = True

    def prever(self, features: Floats) -> Floats:
        x = (features.reshape(len(features), -1) - self.media) / self.desvio
        for i, (w, b) in enumerate(self.camadas):
            x = x @ w + b
            if i < len(self.camadas) - 1:
                x = np.maximum(x, 0)
        resultado: Floats = 1 / (1 + np.exp(-x[:, 0]))
        return resultado


class SemAtivacao:
    """Instalação nova, sem a palavra de ativação treinada: nunca dispara (o Zé atende pelo
    teclado e pelo painel até a pessoa treinar a voz dela; docs/plano-distribuicao.md)."""

    limiar = 1.1
    treinada = False

    def prever(self, features: Floats) -> Floats:
        return np.zeros(len(features), dtype=np.float32)


def carregar_modelo(caminho: Path) -> "ModeloAtivacao | SemAtivacao":
    return ModeloAtivacao(caminho) if caminho.is_file() else SemAtivacao()


class Detector:
    """Dispara uma vez quando `paciencia` quadros seguidos passam do limiar."""

    def __init__(
        self, modelo: "ModeloAtivacao | SemAtivacao", features: Features, paciencia: int = 3
    ) -> None:
        self.modelo = modelo
        self.features = features
        self.limiar = modelo.limiar
        self.paciencia = paciencia
        self.reiniciar()

    def reiniciar(self) -> None:
        self.features.reiniciar()
        self.acertos = 0
        self.ultima_nota = 0.0
        self.nota_disparo = 0.0

    def processar(self, quadro: Audio) -> bool:
        self.features(quadro)
        if len(self.features.buffer) < JANELA:
            return False
        self.ultima_nota = float(self.modelo.prever(self.features.ultimas())[0])
        self.acertos = self.acertos + 1 if self.ultima_nota >= self.limiar else 0
        if self.acertos >= self.paciencia:
            nota = self.ultima_nota
            self.reiniciar()
            self.nota_disparo = nota
            return True
        return False
