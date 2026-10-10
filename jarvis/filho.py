"""Um processo filho do Zé que precisa ficar de pé: sobe, e volta sozinho se cair.

Usado pelo modo imersivo e pelo ai-memory. A espera entre uma queda e a próxima tentativa cresce
até 30 s, para um filho que não sobe não ocupar a máquina.
"""

import logging
import os
import socket
import subprocess
import threading
from collections.abc import Sequence

log = logging.getLogger(__name__)
ESPERA_S = (1.0, 2.0, 5.0, 15.0, 30.0)


def porta_ocupada(porta: int, host: str = "127.0.0.1") -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex((host, porta)) == 0


class Filho:
    def __init__(self, nome: str, comando: Sequence[str], ambiente: dict[str, str]) -> None:
        self.nome = nome
        self.comando = list(comando)
        self.ambiente = ambiente
        self.processo: subprocess.Popen[bytes] | None = None
        self._parar = threading.Event()
        self._fio: threading.Thread | None = None

    def iniciar(self) -> None:
        self._fio = threading.Thread(target=self._manter, name=self.nome, daemon=True)
        self._fio.start()

    def _manter(self) -> None:
        quedas = 0
        while not self._parar.is_set():
            self.processo = subprocess.Popen(  # noqa: S603 (comando montado pelo Zé)
                self.comando,
                env={**os.environ, **self.ambiente},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            log.info("%s subiu", self.nome)
            _, erro = self.processo.communicate()
            if self._parar.is_set():
                return
            final = erro.decode(errors="replace").strip().splitlines()[-1:] or ["sem saída"]
            espera = ESPERA_S[min(quedas, len(ESPERA_S) - 1)]
            log.warning("%s caiu (%s); de novo em %.0f s", self.nome, final[0][:200], espera)
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
