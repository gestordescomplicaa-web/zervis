"""Transporte local (modo mesa): microfone MIC FX por `parec` e saída por `paplay`.

"Microfone fechado" é literal: em INATIVO o processo `parec` não existe, então o PipeWire não
tem nenhum fluxo de gravação do JARVIS (conferível em `pactl list source-outputs`).
"""

import contextlib
import logging
import os
import queue
import subprocess
import threading

log = logging.getLogger(__name__)

SERVIDOR = f"unix:/run/user/{os.getuid()}/pulse/native"
NOME_CLIENTE = "jarvisd"
BYTES_QUADRO = 2560  # 1280 amostras int16 = 80 ms a 16 kHz


class Captura:
    """Quadros de 80 ms numa fila curta; se o laço atrasar, os mais velhos são descartados."""

    def __init__(self, dispositivo: str = "omarchy_mic_fx", tamanho_fila: int = 12) -> None:
        self.dispositivo = dispositivo
        self.quadros: queue.Queue[bytes] = queue.Queue(maxsize=tamanho_fila)
        self.processo: subprocess.Popen[bytes] | None = None
        self._trava = threading.Lock()

    @property
    def aberta(self) -> bool:
        return self.processo is not None and self.processo.poll() is None

    def abrir(self) -> None:
        with self._trava:
            if self.aberta:
                return
            self._esvaziar()
            self.processo = subprocess.Popen(  # noqa: S603 (comando fixo)
                [
                    "/usr/bin/parec",
                    "--server",
                    SERVIDOR,
                    "--device",
                    self.dispositivo,
                    f"--client-name={NOME_CLIENTE}",
                    "--format=s16le",
                    "--rate=16000",
                    "--channels=1",
                    "--latency-msec=80",
                    "--process-time-msec=20",
                    "--raw",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            threading.Thread(target=self._ler, args=(self.processo,), daemon=True).start()
            log.info("microfone aberto")

    def fechar(self) -> None:
        with self._trava:
            processo, self.processo = self.processo, None
            if processo is None:
                return
            processo.terminate()
            try:
                processo.wait(timeout=2)
            except subprocess.TimeoutExpired:
                processo.kill()
                processo.wait()
            self._esvaziar()
            log.info("microfone fechado")

    def _esvaziar(self) -> None:
        while True:
            try:
                self.quadros.get_nowait()
            except queue.Empty:
                return

    def _ler(self, processo: subprocess.Popen[bytes]) -> None:
        assert processo.stdout is not None  # noqa: S101 (criado com PIPE logo acima)
        while True:
            dados = processo.stdout.read(BYTES_QUADRO)
            if len(dados) != BYTES_QUADRO:
                return
            if self.quadros.full():
                with contextlib.suppress(queue.Empty):
                    self.quadros.get_nowait()
            with contextlib.suppress(queue.Full):
                self.quadros.put_nowait(dados)


def comando_reprodutor(taxa: int) -> list[str]:
    return [
        "/usr/bin/paplay",
        "--server",
        SERVIDOR,
        "--device",
        "@DEFAULT_SINK@",
        f"--client-name={NOME_CLIENTE}",
        "--raw",
        "--format=float32le",
        f"--rate={taxa}",
        "--channels=1",
    ]
