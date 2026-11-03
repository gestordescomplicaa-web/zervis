"""Interface compatível do serviço de atendimento."""

from typing import Any

from zervis.cerebro import rapido
from zervis.nucleo.servicos.atendimento import ServicoAtendimento
from zervis.nucleo.servicos.interface import InterfaceServico, servico


class InterfaceAtendimento(InterfaceServico):
    def _mensagem_importante(self, texto: str) -> None:
        servico(self, ServicoAtendimento)._mensagem_importante(texto)

    def _lead_qualificado(self, nome: str, texto: str, telefone: str, chat: str) -> None:
        servico(self, ServicoAtendimento)._lead_qualificado(nome, texto, telefone, chat)

    def _continuar_lead(self, chat: str, texto: str) -> bool:
        return servico(self, ServicoAtendimento)._continuar_lead(chat, texto)

    def _lembrar_leads(self) -> None:
        servico(self, ServicoAtendimento)._lembrar_leads()

    def _leads_ao_celular(self) -> None:
        servico(self, ServicoAtendimento)._leads_ao_celular()

    def ouvir_lead(self, ident: str) -> None:
        servico(self, ServicoAtendimento).ouvir_lead(ident)

    def responder_whatsapp(self, chat: str, nome: str, texto: str) -> str:
        return servico(self, ServicoAtendimento).responder_whatsapp(chat, nome, texto)

    def falar_whatsapp(self, nome: str, argumento: str) -> str:
        return servico(self, ServicoAtendimento).falar_whatsapp(nome, argumento)

    def estado_whatsapp(self) -> dict[str, Any]:
        return servico(self, ServicoAtendimento).estado_whatsapp()

    def dispensar_lead(self, ident: str) -> str:
        return servico(self, ServicoAtendimento).dispensar_lead(ident)

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
