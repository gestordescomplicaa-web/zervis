"""A seção Dispositivos do painel (ADR 0089): os aparelhos da casa num lugar só."""

from typing import Any

from zervis import dispositivos
from zervis.portal.acoes.pagina import Pagina


class AcoesDispositivos(Pagina):
    dependencias = ("camera", "vigia_camera", "impressora3d", "tela_tv")

    def dispositivos(self) -> dict[str, Any]:
        lista = dispositivos.listar(
            self.n.camera, self.n.vigia_camera, self.n.impressora3d, self.n.tela_tv
        )
        cadastrados = {d["id"] for d in lista}
        return {
            "dispositivos": lista,
            "tipos": [t for t in dispositivos.TIPOS if t["id"] not in cadastrados],
        }
