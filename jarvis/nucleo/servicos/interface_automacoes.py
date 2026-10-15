"""Interface compatível do serviço de automacoes."""

from jarvis.automacoes.jobs import Job
from jarvis.nucleo.servicos.automacoes import ServicoAutomacoes
from jarvis.nucleo.servicos.interface import InterfaceServico, servico


class InterfaceAutomacoes(InterfaceServico):
    def _agendador(self, agora: float) -> None:
        servico(self, ServicoAutomacoes)._agendador(agora)

    async def _rodar_pergunta(self, job: Job) -> None:
        await servico(self, ServicoAutomacoes)._rodar_pergunta(job)
