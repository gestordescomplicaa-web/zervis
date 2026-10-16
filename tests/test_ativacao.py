"""Detector "Hey Orca": o MLP em numpy e a regra de paciência.

A equivalência com o openWakeWord original (diferença 0,0 nas 32 gravações do treino e os
mesmos 28 de 30 disparos do JARVIS antigo) é medida por provas/prova_ativacao.py, porque usa a
voz do usuário, que fica fora do repositório.
"""

from pathlib import Path

import numpy as np
import pytest

from jarvis.voz.ativacao import (
    JANELA,
    QUADRO,
    Detector,
    Features,
    ModeloAtivacao,
    SemFeatures,
    SemVAD,
    faltando,
)

MODELOS = Path.home() / ".local/share/zervis/modelos"


def _modelo(tmp_path: Path, limiar: float = 0.7) -> tuple[Path, list[np.ndarray]]:
    caminho = tmp_path / "m.npz"
    rng = np.random.default_rng(0)
    pesos = [
        rng.normal(size=(1536, 4)),
        rng.normal(size=4),
        rng.normal(size=(4, 1)),
        rng.normal(size=1),
    ]
    w0, b0, w1, b1 = pesos
    np.savez(
        caminho,
        depth=2,
        W0=w0,
        b0=b0,
        W1=w1,
        b1=b1,
        mean=np.zeros(1536),
        std=np.ones(1536),
        threshold=limiar,
    )
    return caminho, pesos


def test_mlp_em_numpy_igual_ao_salvo(tmp_path: Path) -> None:
    caminho, (w0, b0, w1, b1) = _modelo(tmp_path)
    modelo = ModeloAtivacao(caminho)
    x = np.random.default_rng(1).normal(size=(3, 16, 96))
    esperado = 1 / (1 + np.exp(-(np.maximum(x.reshape(3, -1) @ w0 + b0, 0) @ w1 + b1)[:, 0]))
    np.testing.assert_allclose(modelo.prever(x.astype(np.float32)), esperado, rtol=1e-5)
    assert modelo.limiar == 0.7


class FeaturesFalsas(Features):
    """Sem ONNX: cada quadro vira um embedding de zeros."""

    def __init__(self) -> None:
        self.reiniciar()

    def __call__(self, quadro: np.ndarray) -> None:
        self.buffer = np.vstack((self.buffer, np.zeros((1, 96), np.float32)))


class ModeloFixo(ModeloAtivacao):
    def __init__(self, notas: list[float]) -> None:
        self.notas, self.limiar = iter(notas), 0.9

    def prever(self, features: np.ndarray) -> np.ndarray:
        return np.array([next(self.notas)], np.float32)


def _quadros(detector: Detector, n: int) -> list[bool]:
    return [detector.processar(np.zeros(QUADRO, np.int16)) for _ in range(n)]


def test_so_pontua_depois_de_uma_janela_cheia_e_pede_paciencia() -> None:
    detector = Detector(ModeloFixo([0.95, 0.95, 0.95, 0.95]), FeaturesFalsas(), paciencia=3)
    resultado = _quadros(detector, JANELA + 2)
    assert resultado == [False] * (JANELA + 2 - 1) + [True]


def test_sem_os_modelos_de_som_o_chamado_nunca_dispara(tmp_path: Path) -> None:
    """Download que falhou (VPS, rede bloqueada): o Zé sobe, e as peças sem modelo ficam inertes,
    em vez de derrubar o núcleo ao carregar um arquivo que não existe (lição de 16/10/2026)."""
    (tmp_path / "silero_vad.onnx").write_bytes(b"")
    assert faltando(tmp_path / "silero_vad.onnx", tmp_path / "smart-turn.onnx") == [
        "smart-turn.onnx"
    ]
    detector = Detector(ModeloFixo([0.99] * 200), SemFeatures(), paciencia=1)
    assert not any(_quadros(detector, JANELA + 5))
    vad = SemVAD()
    vad.reiniciar()
    assert vad.prever(np.ones(QUADRO, np.int16)) == 0.0


def test_uma_nota_baixa_zera_a_paciencia() -> None:
    detector = Detector(ModeloFixo([0.95, 0.95, 0.5, 0.95, 0.95]), FeaturesFalsas(), paciencia=3)
    assert not any(_quadros(detector, JANELA - 1 + 5))


@pytest.mark.skipif(
    not (MODELOS / "embedding_model.onnx").exists(), reason="modelos não instalados"
)
def test_features_reais_de_silencio_sao_estaveis() -> None:
    features = Features(MODELOS / "melspectrogram.onnx", MODELOS / "embedding_model.onnx")
    for _ in range(JANELA):
        features(np.zeros(QUADRO, np.int16))
    assert features.ultimas().shape == (1, JANELA, 96)
    with pytest.raises(ValueError, match="1280"):
        features(np.zeros(10, np.int16))


def test_sem_modelo_treinado_o_ze_sobe_e_nunca_dispara(tmp_path: Path) -> None:
    """Instalação nova: sem a voz treinada, atende pelo teclado e pelo painel."""
    from jarvis.voz.ativacao import SemAtivacao, carregar_modelo

    modelo = carregar_modelo(tmp_path / "nao-existe.npz")
    assert isinstance(modelo, SemAtivacao) and not modelo.treinada
    assert modelo.prever(np.zeros((3, 16, 96), dtype=np.float32)).tolist() == [0.0, 0.0, 0.0]
    assert modelo.limiar > 1  # nem uma nota perfeita passa
