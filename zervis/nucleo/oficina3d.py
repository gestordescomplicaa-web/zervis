"""A oficina 3D do Zé, montada junto com o núcleo: os Projetos 3D (ADR 0082), a impressora na rede
local (ADR 0083) com o vigia dela (ADR 0085) e o Modo TV (ADR 0084)."""

import logging
from collections.abc import Callable
from pathlib import Path

from zervis import lugares, projetos3d
from zervis.impressora3d import Impressora3D
from zervis.impressora_vigia import Vigia
from zervis.projetos3d import Projetos3D
from zervis.tv import TelaTV, TVErro

log = logging.getLogger(__name__)


def montar(
    raiz_projetos: Path,
    acervo: Path,
    dados: Path,
    avisar: Callable[[str], None],
    falando: Callable[[], bool],
) -> tuple[Projetos3D, Impressora3D, Vigia, TelaTV]:
    """Os projetos ao lado dos outros (as prévias no Acervo); a impressora com o vigia conectado
    (o erro, a primeira camada e o fim falados, com foto); e a TV, se o Modo TV estiver ligado."""
    projetos = Projetos3D(
        raiz_projetos / projetos3d.PASTA, acervo, lugares.CONFIG / "projetos3d.json"
    )
    impressora = Impressora3D(lugares.CONFIG / "impressora3d.json")
    vigia = Vigia(impressora, avisar, dados / "impressora" / "fotos")
    impressora.ao_mudar = vigia.iniciar
    vigia.iniciar()
    tela_tv = TelaTV(lugares.CONFIG / "tv.json", acervo, falando=falando)
    try:
        tela_tv.ligar()
    except TVErro as erro:
        log.warning("Modo TV: %s", erro)
    return projetos, impressora, vigia, tela_tv
