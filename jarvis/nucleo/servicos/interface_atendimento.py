"""Interface compatível do serviço de atendimento."""

from typing import Any

from jarvis.cerebro import rapido
from jarvis.nucleo.servicos.atendimento import ServicoAtendimento
from jarvis.nucleo.servicos.interface import InterfaceServico, servico


class InterfaceAtendimento(InterfaceServico):
    def _mensagem_importante(self, texto: str) -> None:
        servico(self, ServicoAtendimento)._mensagem_importante(texto)

    def _motor_das_mensagens(self) -> rapido.Motor:
        return servico(self, ServicoAtendimento)._motor_das_mensagens()

    def _evento_da_central(self, evento: dict[str, Any]) -> None:
        servico(self, ServicoAtendimento)._evento_da_central(evento)

    def _motor_do_atendente(self) -> rapido.Motor:
        return servico(self, ServicoAtendimento)._motor_do_atendente()

    def _atendente_passou(self, nome: str, motivo: str) -> None:
        servico(self, ServicoAtendimento)._atendente_passou(nome, motivo)

    def _subir_central(self) -> None:
        servico(self, ServicoAtendimento)._subir_central()

    def conectar_whatsapp(self) -> str:
        return servico(self, ServicoAtendimento).conectar_whatsapp()

    def desconectar_whatsapp(self) -> str:
        return servico(self, ServicoAtendimento).desconectar_whatsapp()

    def ligar_mensagens(self, ativo: bool) -> str:
        return servico(self, ServicoAtendimento).ligar_mensagens(ativo)
