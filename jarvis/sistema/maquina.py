"""Esta máquina, para a persona: Omarchy com tela e áudio, outro Linux com tela, ou servidor.

A persona dizia "Omarchy, Arch Linux" e "pelo fone" fixo. Numa VPS o cérebro acreditaria estar
num Omarchy e ofereceria volume, janela e brilho que não existem (ADR 0034). O que vale aqui é o
que a máquina tem: as ações do Omarchy, uma sessão gráfica e o áudio local.
"""

import functools
import os
from dataclasses import dataclass
from pathlib import Path

from jarvis.presenca import hyprland
from jarvis.sistema import catalogo


@dataclass(frozen=True)
class Maquina:
    sistema: str  # o nome da distribuição, de /etc/os-release
    omarchy: bool  # há ações do Omarchy no catálogo
    tela: bool  # há uma sessão gráfica
    audio: bool  # há o microfone e o alto-falante locais (PulseAudio ou PipeWire)

    @property
    def servidor(self) -> bool:
        """Sem tela nem áudio: ninguém senta na frente dela, o acesso é sempre de fora."""
        return not (self.omarchy or self.tela or self.audio)

    def para_persona(self) -> str:
        if self.omarchy:
            corpo = (
                f"{self.sistema} com Omarchy, tela e áudio: você opera este computador pelas "
                "ações do Omarchy (seção A máquina)."
            )
        elif self.tela or self.audio:  # o serviço nem sempre recebe DISPLAY da sessão gráfica
            corpo = (
                f"{self.sistema}, com tela, sem as ações do Omarchy: volume, brilho, tema e "
                "janelas deste computador você não muda. Se ele pedir, diga que nesta máquina "
                "isso não está disponível."
            )
        else:
            corpo = (
                f"Um servidor sem tela nem áudio ({self.sistema}). Quem usa fala com você pelo "
                "navegador ou pelo celular e ouve a sua voz por lá. Aqui não há janela, Núcleo na "
                "tela, câmera nem ações do Omarchy: se ele pedir algo da tela ou do computador "
                "dele, diga que neste servidor não dá. As sessões de código trabalham nos "
                "projetos deste servidor."
            )
        return f"## Esta máquina\n{corpo}"


def nome_do_sistema(os_release: Path = Path("/etc/os-release")) -> str:
    try:
        for linha in os_release.read_text().splitlines():
            if linha.startswith("PRETTY_NAME="):
                return linha.split("=", 1)[1].strip().strip("\"'") or "Linux"
    except OSError:
        pass
    return "Linux"


@functools.cache
def detectar() -> Maquina:
    """Uma vez por processo: a máquina não muda enquanto o Zé roda."""
    tela = hyprland.disponivel() or bool(
        os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")
    )
    return Maquina(
        sistema=nome_do_sistema(),
        omarchy=catalogo.tem_omarchy(),
        tela=tela,
        audio=Path("/usr/bin/parec").exists(),
    )
