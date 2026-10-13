"""Um processo filho do Zé que precisa ficar de pé: sobe, e volta sozinho se cair.

Usado pelo modo imersivo e pelo ai-memory. A espera entre uma queda e a próxima tentativa cresce
até 30 s, para um filho que não sobe não ocupar a máquina.
"""

import logging
import os
import signal
import socket
import subprocess
import threading
from collections.abc import Sequence
from pathlib import Path

log = logging.getLogger(__name__)
ESPERA_S = (1.0, 2.0, 5.0, 15.0, 30.0)
ENCERRADO = frozenset({0, -signal.SIGTERM, -signal.SIGINT})


def porta_ocupada(porta: int, host: str = "127.0.0.1") -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex((host, porta)) == 0


class Filho:
    def __init__(
        self,
        nome: str,
        comando: Sequence[str],
        ambiente: dict[str, str],
        registro: Path | None = None,
    ) -> None:
        self.nome = nome
        self.comando = list(comando)
        self.ambiente = ambiente
        self.registro = (
            registro  # a saída do filho num arquivo (diagnóstico), refeito a cada subida
        )
        self.processo: subprocess.Popen[bytes] | None = None
        self._parar = threading.Event()
        self._fio: threading.Thread | None = None

    def iniciar(self) -> None:
        if self.registro is not None:
            self.registro.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._fio = threading.Thread(target=self._manter, name=self.nome, daemon=True)
        self._fio.start()

    def _manter(self) -> None:
        quedas = 0
        while not self._parar.is_set():
            arquivo = self.registro.open("wb") if self.registro is not None else None
            try:
                self.processo = subprocess.Popen(  # noqa: S603 (comando montado pelo Zé)
                    self.comando,
                    env={**os.environ, **self.ambiente},
                    stdout=arquivo or subprocess.DEVNULL,
                    stderr=arquivo or subprocess.PIPE,
                )
                log.info("%s subiu", self.nome)
                _, erro = self.processo.communicate()
            finally:
                if arquivo is not None:
                    arquivo.close()
            if self._parar.is_set():
                return
            if self.registro is not None:
                erro = self.registro.read_bytes()[-2000:]
            final = (erro or b"").decode(errors="replace").strip().splitlines()[-1:] or [
                "sem saída"
            ]
            codigo = self.processo.returncode
            espera = ESPERA_S[min(quedas, len(ESPERA_S) - 1)]
            if codigo in ENCERRADO:
                # Saída ordenada (código 0 ou sinal de término), como quando o serviço inteiro
                # para: não é queda, mas se o Zé segue de pé, o filho volta.
                log.info("%s encerrado (código %s); de novo em %.0f s", self.nome, codigo, espera)
            else:
                log.warning(
                    "%s caiu (código %s: %s); de novo em %.0f s",
                    self.nome,
                    codigo,
                    final[0][:200],
                    espera,
                )
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
