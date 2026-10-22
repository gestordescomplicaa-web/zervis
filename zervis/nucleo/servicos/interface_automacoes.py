"""Interface compatível do serviço de automacoes."""

from zervis.automacoes.jobs import Job
from zervis.nucleo.servicos.automacoes import ServicoAutomacoes
from zervis.nucleo.servicos.interface import InterfaceServico, servico


class InterfaceAutomacoes(InterfaceServico):
    def _agendador(self, agora: float) -> None:
        servico(self, ServicoAutomacoes)._agendador(agora)

    async def _rodar_pergunta(self, job: Job) -> None:
        await servico(self, ServicoAutomacoes)._rodar_pergunta(job)
