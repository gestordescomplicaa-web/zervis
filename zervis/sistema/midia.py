"""O Zé tem a vez: enquanto ouve ou fala, a mídia que estiver tocando pausa e depois volta.

Vídeo e música do navegador (ou de qualquer player) vazam pelo fone para o microfone e o Zé
acaba ouvindo o YouTube como se fosse a pessoa (auditoria de voz, achado 8). Os players do Linux
falam MPRIS pelo D-Bus da sessão; o `busctl` vem com o systemd, sem nada a instalar. Só volta a
tocar o que o próprio Zé pausou, e só se ainda estiver pausado (se a pessoa mexeu, fica como ela
deixou).
"""

import logging
import subprocess
import threading
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

PREFIXO = "org.mpris.MediaPlayer2."
CAMINHO = "/org/mpris/MediaPlayer2"
INTERFACE = "org.mpris.MediaPlayer2.Player"
Rodar = Callable[..., Any]


class Midia:
    def __init__(self, rodar: Rodar = subprocess.run) -> None:
        self.rodar = rodar
        self.pausados: list[str] = []
        self._trava = threading.Lock()

    def _busctl(self, *args: str) -> str:
        r = self.rodar(
            ["busctl", "--user", *args], capture_output=True, text=True, timeout=2, check=False
        )
        return str(r.stdout) if r.returncode == 0 else ""

    def players(self) -> list[str]:
        saida = self._busctl("list", "--no-legend")
        return [
            n for linha in saida.splitlines() if (n := linha.split(" ", 1)[0]).startswith(PREFIXO)
        ]

    def _estado(self, player: str) -> str:
        saida = self._busctl("get-property", player, CAMINHO, INTERFACE, "PlaybackStatus")
        return saida.strip().removeprefix("s ").strip('"')

    def pausar(self) -> None:
        """Pausa o que está tocando e lembra quem foi."""
        with self._trava:
            try:
                for player in self.players():
                    if player not in self.pausados and self._estado(player) == "Playing":
                        self._busctl("call", player, CAMINHO, INTERFACE, "Pause")
                        self.pausados.append(player)
                        log.info("mídia pausada: %s", player.removeprefix(PREFIXO))
            except (OSError, subprocess.SubprocessError) as erro:
                log.warning("mídia: %s", erro)

    def retomar(self) -> None:
        """Volta a tocar só o que o Zé pausou e continua pausado."""
        with self._trava:
            pausados, self.pausados = self.pausados, []
            try:
                for player in pausados:
                    if self._estado(player) == "Paused":
                        self._busctl("call", player, CAMINHO, INTERFACE, "Play")
            except (OSError, subprocess.SubprocessError) as erro:
                log.warning("mídia: %s", erro)
