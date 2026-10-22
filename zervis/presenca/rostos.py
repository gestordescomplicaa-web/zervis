"""Rostos: o que liga o Zé (ADR 0021, generaliza o ADR 0003).

Um rosto é qualquer coisa que diz "a pessoa está aqui": a janela do Zé aberta no Hyprland, a
escuta sempre ligada, um dispositivo conectado pela voz remota. O Zé fica ativo (microfone aberto
para o chamado) enquanto existir pelo menos um rosto, e volta a inativo quando o último sai.
"""

import threading
from collections.abc import Callable


class Rostos:
    """Junta os rostos e avisa `ao_mudar(ativo)` só quando o conjunto muda de vazio para não."""

    def __init__(self, ao_mudar: Callable[[bool], None]) -> None:
        self.ao_mudar = ao_mudar
        self._ativos: set[str] = set()
        self._avisado: bool | None = None
        self._trava = threading.Lock()

    @property
    def ativos(self) -> frozenset[str]:
        with self._trava:
            return frozenset(self._ativos)

    def marcar(self, nome: str, ativo: bool) -> None:
        with self._trava:
            if ativo:
                self._ativos.add(nome)
            else:
                self._ativos.discard(nome)
            agora = bool(self._ativos)
            if agora == self._avisado:
                return
            self._avisado = agora
        self.ao_mudar(agora)
