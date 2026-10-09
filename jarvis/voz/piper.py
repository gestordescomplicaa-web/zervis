"""A voz do Zé: Cadu pelo Piper, dentro do próprio processo (ADR 0013).

O `piper-tts` (GPL-3) é dependência do projeto e a voz `pt_BR-cadu-medium` (CC0) é baixada e
conferida na primeira subida (`jarvis/preparar.py`), junto com os modelos de som. Sem servidor à
parte: a voz fica carregada na memória e o Piper entrega o áudio frase a frase, então a primeira
frase toca enquanto as seguintes ainda estão sendo sintetizadas.

Otimização medida (Ryzen 5 8500G, 6 núcleos e 12 threads, 09/10/2026): com o padrão do
onnxruntime (todas as threads lógicas) a primeira frase saía em ~270 ms; com uma thread por núcleo
físico, até 4, sai em ~130 ms. Mais threads que isso disputam o mesmo núcleo e pioram.
"""

import json
import os
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from jarvis import lugares

if TYPE_CHECKING:
    from piper import PiperVoice

VOZ = "pt_BR-cadu-medium.onnx"


def threads() -> int:
    """Uma por núcleo físico (metade das lógicas, com SMT), no máximo 4."""
    return max(1, min(4, (os.cpu_count() or 2) // 2))


class FluxoGerado:
    """O áudio (float32) de cada frase conforme o Piper termina; `b""` no fim."""

    def __init__(self, partes: Iterator[bytes]) -> None:
        self.partes: Iterator[bytes] | None = partes

    def read1(self, n: int = -1, /) -> bytes:
        if self.partes is None:
            return b""
        try:
            return next(self.partes)
        except StopIteration:
            self.partes = None
            return b""

    def close(self) -> None:
        self.partes = None  # parar(): as frases que faltam nem chegam a ser sintetizadas


class Piper:
    def __init__(self, modelo: Path) -> None:
        self.modelo = modelo
        self._voz: PiperVoice | None = None
        self._trava = threading.Lock()

    def carregar(self) -> "PiperVoice":
        """Carrega a voz uma vez (cerca de um segundo); as falas seguintes já a encontram pronta."""
        with self._trava:
            if self._voz is None:
                if not self.modelo.is_file():
                    raise RuntimeError(f"voz do Piper não encontrada em {self.modelo}")
                import onnxruntime  # só quem fala paga a carga do Piper
                from piper import PiperVoice
                from piper.config import PiperConfig

                opcoes = onnxruntime.SessionOptions()
                opcoes.intra_op_num_threads = threads()
                config = json.loads(Path(f"{self.modelo}.json").read_text(encoding="utf-8"))
                self._voz = PiperVoice(
                    config=PiperConfig.from_dict(config),
                    session=onnxruntime.InferenceSession(
                        str(self.modelo), sess_options=opcoes, providers=["CPUExecutionProvider"]
                    ),
                )
            return self._voz

    def _frases(self, voz: "PiperVoice", texto: str) -> Iterator[bytes]:
        for pedaco in voz.synthesize(texto):
            yield pedaco.audio_float_array.astype("<f4").tobytes()

    def abrir_fluxo(self, texto: str) -> tuple[int, FluxoGerado]:
        voz = self.carregar()
        return voz.config.sample_rate, FluxoGerado(self._frases(voz, texto))

    def sintetizar(self, texto: str) -> tuple[int, np.ndarray]:
        """A fala inteira de uma vez (treino da palavra de ativação)."""
        taxa, fluxo = self.abrir_fluxo(texto)
        dados = b"".join(iter(fluxo.read1, b""))
        return taxa, np.frombuffer(dados, "<f4")


PADRAO = Piper(lugares.DADOS / "modelos" / VOZ)
