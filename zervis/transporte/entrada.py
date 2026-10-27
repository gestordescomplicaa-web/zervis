"""A entrada de áudio do laço: o microfone local ou a voz remota, numa fila só.

O laço lê quadros de 80 ms de `quadros` e abre ou fecha a entrada conforme a máquina de estados,
sem saber de onde o áudio vem. Com a voz remota conectada, ela tem a vez: o microfone local
fecha, para a mesma fala não chegar duas vezes (pelo PC e pelo celular); quando ela sai, o
microfone local volta se a entrada ainda estiver aberta.
"""

import contextlib
import queue
import threading

from zervis.transporte.local import Captura


class Entrada:
    def __init__(self, local: Captura) -> None:
        self.local = local
        self.quadros = local.quadros
        self.remota_ligada = False
        self._aberta = False
        self._trava = threading.Lock()

    @property
    def aberta(self) -> bool:
        return self._aberta

    def abrir(self) -> None:
        with self._trava:
            self._aberta = True
            if not self.remota_ligada:
                self.local.abrir()

    def fechar(self) -> None:
        with self._trava:
            self._aberta = False
            self.local.fechar()

    def remota(self, ligada: bool) -> None:
        with self._trava:
            self.remota_ligada = ligada
            if not self._aberta:
                return
            if ligada:
                self.local.fechar()
            else:
                self.local.abrir()

    def receber(self, quadro: bytes) -> None:
        """Um quadro da voz remota; descartado com a entrada fechada, como o microfone fechado."""
        if not (self._aberta and self.remota_ligada):
            return
        if self.quadros.full():
            with contextlib.suppress(queue.Empty):
                self.quadros.get_nowait()
        with contextlib.suppress(queue.Full):
            self.quadros.put_nowait(quadro)
