"""Interface compatível do serviço de avisos."""

from jarvis.avisos import modo as modo_fala
from jarvis.nucleo import estados as e
from jarvis.nucleo.servicos.avisos import ServicoAvisos
from jarvis.nucleo.servicos.interface import InterfaceServico, servico


class InterfaceAvisos(InterfaceServico):
    def _bom_dia(self) -> None:
        servico(self, ServicoAvisos)._bom_dia()

    async def _narrar_fim(
        self, id_: str, nome: str, resposta: str, titulo: str, detalhe: str, pedido: str = ""
    ) -> None:
        await servico(self, ServicoAvisos)._narrar_fim(id_, nome, resposta, titulo, detalhe, pedido)

    def _ultima_resposta(self, id_: str) -> str:
        return servico(self, ServicoAvisos)._ultima_resposta(id_)

    def vendo(self, id_: str) -> bool:
        return servico(self, ServicoAvisos).vendo(id_)

    def ver_sessao(self, id_: str) -> None:
        servico(self, ServicoAvisos).ver_sessao(id_)

    def mudar_modo_fala(self, modo: str) -> str:
        return servico(self, ServicoAvisos).mudar_modo_fala(modo)

    def _aviso_da_oficina(
        self, texto: str, tipo: modo_fala.Tipo, id_: str = "", titulo: str = "", detalhe: str = ""
    ) -> None:
        servico(self, ServicoAvisos)._aviso_da_oficina(texto, tipo, id_, titulo, detalhe)

    def _guardar(self, texto: str) -> None:
        servico(self, ServicoAvisos)._guardar(texto)

    def _sair_da_fila(self) -> None:
        servico(self, ServicoAvisos)._sair_da_fila()

    def _antes_de_avisar(self, texto: str) -> None:
        servico(self, ServicoAvisos)._antes_de_avisar(texto)

    def _proximo_aviso(self) -> str:
        return servico(self, ServicoAvisos)._proximo_aviso()

    def _detalhe_do_aviso(self) -> str:
        return servico(self, ServicoAvisos)._detalhe_do_aviso()

    def _regras_de_fala(self, aviso: e.Aviso) -> e.Aviso | None:
        return servico(self, ServicoAvisos)._regras_de_fala(aviso)

    def _pessoa_falando(self) -> bool:
        return servico(self, ServicoAvisos)._pessoa_falando()

    def _aviso_ao_vivo(self) -> None:
        servico(self, ServicoAvisos)._aviso_ao_vivo()

    def _com_avisos(self, texto: str) -> str:
        return servico(self, ServicoAvisos)._com_avisos(texto)
