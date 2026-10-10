"""O modo imersivo do Zé: o holograma, os orbes e a tela movida pelas mãos (ADR 0014).

Vem do Barehands (Jared Rhodenizer, AGPL-3.0) modificado para o Zé; ver THIRD_PARTY.md. O Zé
sobe o servidor (`servidor.py`) como processo filho e o reinicia se cair; a página fica em `web/`.
"""

import logging
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

log = logging.getLogger(__name__)
PORTA = 8794
ESPERA_S = (1.0, 2.0, 5.0, 15.0, 30.0)  # entre uma queda e a próxima tentativa


def porta_ocupada(porta: int = PORTA) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", porta)) == 0


class Imersivo:
    """O servidor do modo imersivo como processo filho do Zé, com o estado em `pasta_estado`."""

    def __init__(self, pasta_estado: Path, porta: int = PORTA) -> None:
        self.pasta_estado = pasta_estado
        self.porta = porta
        self.processo: subprocess.Popen[bytes] | None = None
        self._parar = threading.Event()
        self._fio: threading.Thread | None = None

    def iniciar(self) -> None:
        if porta_ocupada(self.porta):
            log.warning("modo imersivo: porta %d já em uso; o Zé não sobe o próprio", self.porta)
            return
        self._fio = threading.Thread(target=self._manter, name="imersivo", daemon=True)
        self._fio.start()

    def _manter(self) -> None:
        quedas = 0
        while not self._parar.is_set():
            ambiente = {
                **os.environ,
                "ZE_IMERSIVO_ESTADO": str(self.pasta_estado),
                "ZE_IMERSIVO_PORTA": str(self.porta),
            }
            self.processo = subprocess.Popen(
                [sys.executable, "-m", "jarvis.imersivo.servidor"],
                env=ambiente,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            log.info("modo imersivo em http://127.0.0.1:%d/stage.html", self.porta)
            _, erro = self.processo.communicate()
            if self._parar.is_set():
                return
            final = erro.decode(errors="replace").strip().splitlines()[-1:] or ["sem saída"]
            espera = ESPERA_S[min(quedas, len(ESPERA_S) - 1)]
            log.warning("modo imersivo caiu (%s); de novo em %.0f s", final[0][:200], espera)
            quedas += 1
            self._parar.wait(espera)

    def parar(self) -> None:
        self._parar.set()
        if self.processo is not None and self.processo.poll() is None:
            self.processo.terminate()
            try:
                self.processo.wait(5)
            except subprocess.TimeoutExpired:
                self.processo.kill()
