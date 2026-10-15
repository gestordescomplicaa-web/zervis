"""Interface compatível do serviço de oficina."""

from typing import Any

from jarvis.nucleo.servicos.interface import InterfaceServico, servico
from jarvis.nucleo.servicos.oficina import ServicoOficina
from jarvis.oficina.sessoes import Sessao


class InterfaceOficina(InterfaceServico):
    def _contexto_da_manutencao(self) -> str:
        return servico(self, ServicoOficina)._contexto_da_manutencao()

    @staticmethod
    def _descrever_manutencao(nome: str, entrada: dict[str, Any]) -> str | None:
        return ServicoOficina._descrever_manutencao(nome, entrada)

    def diagnosticar(self, registro: list[str]) -> tuple[str, str]:
        return servico(self, ServicoOficina).diagnosticar(registro)

    def recomecar_diagnostico(self) -> str:
        return servico(self, ServicoOficina).recomecar_diagnostico()

    def _outras_trabalhando(self) -> list[str]:
        return servico(self, ServicoOficina)._outras_trabalhando()

    def mudar_manutencao(self, ligar: bool) -> str:
        return servico(self, ServicoOficina).mudar_manutencao(ligar)

    def _aplicar_quando_livre(self) -> None:
        servico(self, ServicoOficina)._aplicar_quando_livre()

    def aplicar_melhorias(self, revisado: bool = False) -> str:
        return servico(self, ServicoOficina).aplicar_melhorias(revisado)

    def _rodada_de_melhoria(self) -> str:
        return servico(self, ServicoOficina)._rodada_de_melhoria()

    def _manutencao_chegou(self, agora: float) -> None:
        servico(self, ServicoOficina)._manutencao_chegou(agora)

    def _sessao_terminou(self, sessao: Sessao, resumo: str) -> None:
        servico(self, ServicoOficina)._sessao_terminou(sessao, resumo)

    def _sessao_pede(self, sessao: Sessao, mensagem: str) -> None:
        servico(self, ServicoOficina)._sessao_pede(sessao, mensagem)

    def _avisar_interrompidas(self) -> None:
        servico(self, ServicoOficina)._avisar_interrompidas()
