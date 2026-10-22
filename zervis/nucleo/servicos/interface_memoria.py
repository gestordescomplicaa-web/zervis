"""Interface compatível do serviço de memoria."""

from typing import Any

from zervis.nucleo.servicos.interface import InterfaceServico, servico
from zervis.nucleo.servicos.memoria import ServicoMemoria
from zervis.rosto import pasta


class InterfaceMemoria(InterfaceServico):
    def _na_linha(self, tipo: str, texto: str) -> None:
        servico(self, ServicoMemoria)._na_linha(tipo, texto)

    def _foto_simples(self) -> str:
        return servico(self, ServicoMemoria)._foto_simples()

    def _foto_do_cerebro(self) -> str:
        return servico(self, ServicoMemoria)._foto_do_cerebro()

    def _com_memoria(self, pedido: str) -> str:
        return servico(self, ServicoMemoria)._com_memoria(pedido)

    def _registrar_turno(self, turno: dict[str, str]) -> None:
        servico(self, ServicoMemoria)._registrar_turno(turno)

    def _nota_do_dia(self, agora: float) -> None:
        servico(self, ServicoMemoria)._nota_do_dia(agora)

    async def _escrever_notas(self, dias: list[Any]) -> None:
        await servico(self, ServicoMemoria)._escrever_notas(dias)

    def _conversa_parada(self) -> None:
        servico(self, ServicoMemoria)._conversa_parada()

    def _atualizar_pasta(self, agora: float) -> None:
        servico(self, ServicoMemoria)._atualizar_pasta(agora)

    def _escrever_pasta(self, conexoes: pasta.Conexoes, curar: bool) -> None:
        servico(self, ServicoMemoria)._escrever_pasta(conexoes, curar)
