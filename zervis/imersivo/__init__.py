"""O modo imersivo do Zé: o holograma, os orbes e a tela movida pelas mãos (ADR 0014).

Vem do Barehands (Jared Rhodenizer, AGPL-3.0) modificado para o Zé; ver THIRD_PARTY.md. O Zé
sobe o servidor (`servidor.py`) como processo filho e o reinicia se cair; a página fica em `web/`.
"""

import logging
import secrets
import subprocess
import sys
from pathlib import Path

from zervis import lugares
from zervis.filho import Filho, porta_ocupada

log = logging.getLogger(__name__)
PORTA = 8794
# O Acervo: a pasta do Zé com o que ele mostra na tela. Imagens e modelos 3D por enquanto.
PASTAS_ACERVO = ("imagens", "3d")
TIPOS_ACERVO = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif", ".glb", ".gltf"})


def tem_acervo(pasta: Path) -> bool:
    """Há ao menos um arquivo aceito no Acervo (sem isso, o orbe não aparece)."""
    try:
        return any(p.suffix.lower() in TIPOS_ACERVO for p in pasta.rglob("*") if p.is_file())
    except OSError:
        return False


class Imersivo:
    """O servidor do modo imersivo como processo filho do Zé, com o estado em `pasta_estado`."""

    def __init__(self, pasta_estado: Path, porta: int = PORTA, acervo: Path | None = None) -> None:
        self.pasta_estado = pasta_estado
        self.porta = porta
        self.acervo = acervo or pasta_estado.parent / "acervo"
        self.token = secrets.token_urlsafe(32)
        self.filho = Filho(
            "modo imersivo",
            [sys.executable, "-m", "zervis.imersivo.servidor"],
            {
                "ZE_IMERSIVO_ESTADO": str(self.pasta_estado),
                "ZE_IMERSIVO_PORTA": str(self.porta),
                "ZE_ACERVO": str(self.acervo),
                "ZE_IMERSIVO_TOKEN": self.token,
            },
            registro=lugares.ESTADO / "imersivo.log",
        )

    @property
    def processo(self) -> "subprocess.Popen[bytes] | None":
        return self.filho.processo

    def iniciar(self) -> None:
        if porta_ocupada(self.porta):
            log.warning("modo imersivo: porta %d já em uso; o Zé não sobe o próprio", self.porta)
            return
        log.info("modo imersivo em http://127.0.0.1:%d/stage.html", self.porta)
        self.filho.iniciar()

    def parar(self) -> None:
        self.filho.parar()
