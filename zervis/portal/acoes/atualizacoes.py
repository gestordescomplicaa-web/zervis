"""Ações da página atualizacoes: procurar, escolher o canal e atualizar (`zervis/versoes.py`)."""

from typing import Any

from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido


class AcoesAtualizacoes(Pagina):
    dependencias = ("atualizacao", "sessoes", "versoes")

    def atualizacoes(self) -> dict[str, Any]:
        return {
            "canal": self.n.versoes.canal,
            "ultima": self.n.versoes.ultima(),
            "resultado": self.n.versoes.ultimo_resultado(),
        }

    def procurar_atualizacao(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.n.versoes.procurar()
        return self.painel.atualizacoes()

    def canal_de_atualizacao(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            self.n.versoes.mudar_canal(str(dados.get("canal", "")))
        except ValueError:
            raise PedidoInvalido("Canal desconhecido.") from None
        return self.painel.procurar_atualizacao({})

    def aplicar_atualizacao(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Atualiza só sem cortar ninguém: o reinício derrubaria uma sessão no meio da tarefa."""
        if self.n.atualizacao.reserva() is not None:
            raise PedidoInvalido("O autodesenvolvimento está aplicando melhorias agora.")
        if trabalhando := self.n.sessoes.trabalhando():
            quantas = (
                "Uma sessão está" if len(trabalhando) == 1 else f"{len(trabalhando)} sessões estão"
            )
            raise PedidoInvalido(f"{quantas} trabalhando. Atualize quando terminarem.")
        achado = self.n.versoes.procurar()
        if not achado["disponivel"]:
            raise PedidoInvalido(achado["texto"] or "Não há atualização para aplicar.")
        texto = self.n.versoes.aplicar()
        return {**self.painel.atualizacoes(), "aviso": texto}
