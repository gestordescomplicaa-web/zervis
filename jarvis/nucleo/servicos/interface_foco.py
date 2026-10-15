"""Interface compatível do serviço de foco."""

from typing import Any

from jarvis.foco.frentes import Frente
from jarvis.nucleo.servicos.foco import ServicoFoco
from jarvis.nucleo.servicos.interface import InterfaceServico, servico


class InterfaceFoco(InterfaceServico):
    def _foco_mudou(self, o_que: str, frente: Frente) -> None:
        servico(self, ServicoFoco)._foco_mudou(o_que, frente)

    def _mostrar(self, texto: str) -> None:
        servico(self, ServicoFoco)._mostrar(texto)

    def _foco_na_tela(self, agora: float) -> None:
        servico(self, ServicoFoco)._foco_na_tela(agora)

    def _evento_da_tela(self) -> None:
        servico(self, ServicoFoco)._evento_da_tela()

    def _abrir_item(self, argumento: str) -> None:
        servico(self, ServicoFoco)._abrir_item(argumento)

    def _comando_especial(self, nome: str, argumento: str) -> str:
        return servico(self, ServicoFoco)._comando_especial(nome, argumento)

    def _se_aberto(self, acoes: list[dict[str, Any]], pronto: str) -> str:
        return servico(self, ServicoFoco)._se_aberto(acoes, pronto)

    def _no_nucleo(self, acoes: list[dict[str, Any]], pronto: str = "Está no Núcleo.") -> str:
        return servico(self, ServicoFoco)._no_nucleo(acoes, pronto)

    def _com_foco(self, texto: str) -> str:
        return servico(self, ServicoFoco)._com_foco(texto)
