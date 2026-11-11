"""Anel do Barehands: `state/state`, `state/mood.json`, `state/wave.json`, `state/expressao.json` e
`state/fala.json` (só o Zé escreve). A expressão é a emoção do avatar (08/10/2026): o cérebro
começa a resposta com `[alegria]`, `[duvida]`, `[raiva]` ou `[tristeza]`; a marca sai antes da voz e
vira o rosto.

Portado de VIBE-CODING/jarvis/ring.py (06/10/2026). O Barehands esquece um estado não ocioso
depois de dez minutos e um humor depois de 45 s, então esperas longas pedem reescrita
periódica, não só na mudança.

`fala.json` (11/11/2026): o pedaço de fala que está tocando e até que caractere ele já foi dito,
para a cena do "explicar" (jarvis-cenas.js) mostrar cada passo quando o Zé chega à frase dele.
"""

import contextlib
import json
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

Amostras = NDArray[np.float32]
EMOCOES = ("alegria", "duvida", "raiva", "tristeza")
FALA_S = 0.065  # ~65 ms de fala por caractere (zervis/voz/saida.py)
SEGURAR_S = 12.0  # o rosto segura a emoção durante a resposta e volta sozinho ao neutro
_MARCA = re.compile(r"^\s*\[\s*(alegria|d[uú]vida|raiva|tristeza|neutro)\s*\]\s*", re.IGNORECASE)


def separar_emocao(texto: str) -> tuple[str, str]:
    """`[alegria] Que bom!` vira ("alegria", "Que bom!"); sem marca, ("", texto)."""
    marca = _MARCA.match(texto)
    if not marca:
        return "", texto
    return marca[1].lower().replace("ú", "u"), texto[marca.end() :]


def onda_em(amostras: Amostras, taxa: int, segundos: float, n: int = 64) -> list[float] | None:
    """64 amostras da janela de 50 ms em `segundos`; None se o áudio ainda não chegou lá."""
    inicio = int(segundos * taxa)
    if inicio >= len(amostras):
        return None
    passo = max(n, int(0.05 * taxa)) // n
    indices = inicio + np.arange(n) * passo
    escolhidas = np.where(
        indices < len(amostras), amostras[np.minimum(indices, len(amostras) - 1)], 0
    )
    return [round(float(v), 3) for v in escolhidas]


def falado_ate(texto: str, tocado_s: float, gerado_s: float, gerando: bool) -> int:
    """Até que caractere de `texto` a voz chegou, `tocado_s` depois de começar.

    A duração é a do áudio já gerado; enquanto ele ainda cresce, no mínimo a estimativa pelo
    tamanho do texto (senão o começo de um pedaço longo pareceria já perto do fim).
    """
    duracao = max(gerado_s, len(texto) * FALA_S if gerando else 0.0)
    if duracao <= 0:
        return 0
    return round(len(texto) * min(1.0, max(0.0, tocado_s) / duracao))


class Anel:
    def __init__(self, pasta: Path, intervalo: float = 0.06) -> None:
        self.pasta = pasta
        self.intervalo = intervalo
        self.mostrado: tuple[str, str] | None = None
        self.renovado = 0.0
        self._onda: threading.Event | None = None

    def _escrever(self, nome: str, texto: str) -> None:
        temporario = self.pasta / (nome + ".next")
        temporario.write_text(texto)
        temporario.replace(self.pasta / nome)

    def mostrar(self, estado: str, humor: str, agora: float) -> None:
        if not self.pasta.is_dir():
            return
        if (estado, humor) == self.mostrado and agora - self.renovado < 20:
            return
        try:
            self._escrever("state", estado)
            self._escrever("mood.json", json.dumps({"mood": humor, "ts": agora}))
        except OSError:
            return
        self.mostrado = (estado, humor)
        self.renovado = agora

    def expressao(self, nome: str, agora: float, segundos: float = SEGURAR_S) -> None:
        """O rosto do avatar até `agora + segundos`; "neutro" (ou outro nome) solta na hora."""
        if not self.pasta.is_dir():
            return
        ate = agora + segundos if nome in EMOCOES else 0.0
        with contextlib.suppress(OSError):
            self._escrever("expressao.json", json.dumps({"expressao": nome, "ate": ate}))

    def comecar(self, amostras: Callable[[], Amostras], taxa: int, texto: str = "") -> None:
        """`amostras()` devolve o PCM tocado até agora (pode crescer durante o streaming);
        `texto` é o que esse pedaço diz (vai para `fala.json`)."""
        self.parar()
        if not self.pasta.is_dir():
            return
        parar = threading.Event()
        self._onda = parar

        def rodar() -> None:
            inicio, comeco, gerado, quadros = time.monotonic(), time.time(), -1.0, 0
            while not parar.is_set():
                pcm = amostras()
                tocado = time.monotonic() - inicio
                quadro = onda_em(pcm, taxa, tocado)
                if quadro is not None:
                    with contextlib.suppress(OSError):
                        self._escrever(
                            "wave.json", json.dumps({"samples": quadro, "ts": time.time()})
                        )
                if texto and quadros % 3 == 0:  # ~5 vezes por segundo basta para a cena
                    agora_gerado = len(pcm) / taxa
                    ate = falado_ate(texto, tocado, agora_gerado, agora_gerado != gerado)
                    gerado = agora_gerado
                    with contextlib.suppress(OSError):
                        self._escrever(
                            "fala.json",
                            json.dumps(
                                {"texto": texto, "ate": ate, "inicio": comeco, "ts": time.time()},
                                ensure_ascii=False,
                            ),
                        )
                quadros += 1
                parar.wait(self.intervalo)

        threading.Thread(target=rodar, name="anel-onda", daemon=True).start()

    def parar(self) -> None:
        if self._onda:
            self._onda.set()
            self._onda = None
