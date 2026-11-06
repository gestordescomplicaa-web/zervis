"""Interface compatível do serviço de automacoes."""

from zervis.automacoes.jobs import Execucao
from zervis.nucleo.servicos.automacoes import ServicoAutomacoes
from zervis.nucleo.servicos.interface import InterfaceServico, servico


class InterfaceAutomacoes(InterfaceServico):
    def _agendador(self, agora: float) -> None:
        servico(self, ServicoAutomacoes)._agendador(agora)

    async def _rodar_pergunta(self, x: Execucao) -> None:
        await servico(self, ServicoAutomacoes)._rodar_pergunta(x)

    def _retomar_execucoes(self) -> None:
        servico(self, ServicoAutomacoes).retomar_execucoes()
