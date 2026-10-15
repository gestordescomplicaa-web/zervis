"""Interface compatível do serviço de voz."""

import concurrent.futures
from pathlib import Path

from jarvis.nucleo import estados as e
from jarvis.nucleo.servicos.interface import InterfaceServico, servico
from jarvis.nucleo.servicos.voz import ServicoVoz
from jarvis.voz.deepgram import EscutaDeepgram


class InterfaceVoz(InterfaceServico):
    def _voz_ociosa(self, numero: int) -> None:
        servico(self, ServicoVoz)._voz_ociosa(numero)

    def _transcrito(self, futuro: concurrent.futures.Future[str], turno: str | None = None) -> None:
        servico(self, ServicoVoz)._transcrito(futuro, turno)

    def _abrir_latencia(self, rota: str) -> None:
        servico(self, ServicoVoz)._abrir_latencia(rota)

    def _fechar_latencia(self, resultado: str = "concluido") -> None:
        servico(self, ServicoVoz)._fechar_latencia(resultado)

    def mudar_escuta(self, modo: str) -> str:
        return servico(self, ServicoVoz).mudar_escuta(modo)

    def _carregar_voz(self) -> None:
        servico(self, ServicoVoz)._carregar_voz()

    def _tocar_bip(self) -> None:
        servico(self, ServicoVoz)._tocar_bip()

    def _tocar_som(self, som: Path) -> None:
        servico(self, ServicoVoz)._tocar_som(som)

    def _descartar_escuta(self) -> None:
        servico(self, ServicoVoz)._descartar_escuta()

    def _guardar_chamado(self, ignorado: bool = False) -> None:
        servico(self, ServicoVoz)._guardar_chamado(ignorado)

    def _pausar_midia(self) -> bool:
        return servico(self, ServicoVoz)._pausar_midia()

    def _dar_a_vez(self, antes: e.Estado, depois: e.Estado) -> None:
        servico(self, ServicoVoz)._dar_a_vez(antes, depois)

    def _ninguem_falou(self) -> bool:
        return servico(self, ServicoVoz)._ninguem_falou()

    def _pedido_fechado(self, trecho: bytes, por: str = "") -> None:
        servico(self, ServicoVoz)._pedido_fechado(trecho, por)

    def _fechar_pelo_botao(self) -> None:
        servico(self, ServicoVoz)._fechar_pelo_botao()

    @property
    def microfone_travado(self) -> bool:
        return servico(self, ServicoVoz).microfone_travado

    def apertar(self) -> None:
        servico(self, ServicoVoz).apertar()

    def soltar(self) -> None:
        servico(self, ServicoVoz).soltar()

    def _aplicar_espera(self) -> None:
        servico(self, ServicoVoz)._aplicar_espera()

    def mudar_espera(self, modo: str) -> str:
        return servico(self, ServicoVoz).mudar_espera(modo)

    def mudar_chamado(self, modo: str) -> str:
        return servico(self, ServicoVoz).mudar_chamado(modo)

    def _fechar_escuta(self) -> None:
        servico(self, ServicoVoz)._fechar_escuta()

    def _transcrever(self, trecho: bytes, escuta: EscutaDeepgram | None) -> str:
        return servico(self, ServicoVoz)._transcrever(trecho, escuta)

    def _ligar_ativacao(self) -> None:
        servico(self, ServicoVoz)._ligar_ativacao()

    def aplicar_escuta(self) -> None:
        servico(self, ServicoVoz).aplicar_escuta()
