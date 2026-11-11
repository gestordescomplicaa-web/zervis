"""Ações do cartão Abertura, na página Perfil (ADR 0078): ligada, a cidade do clima e a música."""

import time
from typing import Any

from zervis import fuso
from zervis.abertura import ajustes
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido


class AcoesAbertura(Pagina):
    dependencias = ("abertura",)

    def abertura(self) -> dict[str, Any]:
        a = ajustes.ler()
        return {
            "ligada": a.ligada,
            "cidade": a.cidade,
            "cidade_do_fuso": ajustes.cidade_do_fuso(str(fuso.local())),
            "musica": ajustes.musica() is not None,
        }

    def _depois(self, aviso: str) -> dict[str, Any]:
        self.n.abertura.retratar(time.time(), ja=True)  # a próxima abertura já vem com o ajuste
        return {**self.abertura(), "aviso": aviso}

    def salvar_abertura(self, dados: dict[str, Any]) -> dict[str, Any]:
        cidade = str(dados.get("cidade", "")).strip()
        if len(cidade) > 80:
            raise PedidoInvalido("Cidade com mais de 80 caracteres.")
        ajustes.gravar(ajustes.Ajustes(dados.get("ligada") is not False, cidade))
        return self._depois("Abertura salva.")

    def enviar_musica(self, corpo: bytes, _consulta: dict[str, str]) -> dict[str, Any]:
        try:
            ajustes.guardar_musica(corpo)
        except ajustes.AjusteErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return self._depois("Música salva.")

    def remover_musica(self, _dados: dict[str, Any]) -> dict[str, Any]:
        ajustes.remover_musica()
        return self._depois("Música removida.")
