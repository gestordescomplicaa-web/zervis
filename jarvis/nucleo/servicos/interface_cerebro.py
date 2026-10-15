"""Interface compatível do serviço de cerebro."""

from jarvis import usuario
from jarvis.cerebro.base import Brain
from jarvis.cerebro.baterias import Bateria
from jarvis.nucleo.servicos.cerebro import ServicoCerebro
from jarvis.nucleo.servicos.interface import InterfaceServico, servico


class InterfaceCerebro(InterfaceServico):
    def _latencia_do_cerebro(self, marca: int) -> str | None:
        return servico(self, ServicoCerebro)._latencia_do_cerebro(marca)

    def _primeiro_texto_do_cerebro(self, marca: int, em: float) -> None:
        servico(self, ServicoCerebro)._primeiro_texto_do_cerebro(marca, em)

    def _frase_do_cerebro(self, marca: int, frase: str) -> None:
        servico(self, ServicoCerebro)._frase_do_cerebro(marca, frase)

    def _pedido_de_aprovacao(self, marca: int, descricao: str) -> None:
        servico(self, ServicoCerebro)._pedido_de_aprovacao(marca, descricao)

    def _fim_do_cerebro(self, marca: int, erro: str | None) -> None:
        servico(self, ServicoCerebro)._fim_do_cerebro(marca, erro)

    def _com_via_rapida(self, cerebro: Brain) -> Brain:
        return servico(self, ServicoCerebro)._com_via_rapida(cerebro)

    def recarregar_conectores(self) -> str:
        return servico(self, ServicoCerebro).recarregar_conectores()

    def persona(self) -> str:
        return servico(self, ServicoCerebro).persona()

    def aplicar_perfil(self, perfil: usuario.Perfil) -> str:
        return servico(self, ServicoCerebro).aplicar_perfil(perfil)

    def aplicar_acesso(self) -> str:
        return servico(self, ServicoCerebro).aplicar_acesso()

    def _remontar(self) -> str:
        return servico(self, ServicoCerebro)._remontar()

    def persona_rapida(self) -> str:
        return servico(self, ServicoCerebro).persona_rapida()

    def aplicar_via_rapida(self) -> str:
        return servico(self, ServicoCerebro).aplicar_via_rapida()

    def trocar_cerebro(self, id_: str) -> str:
        return servico(self, ServicoCerebro).trocar_cerebro(id_)

    def _testar_modelo(self, modelo: str) -> str | None:
        return servico(self, ServicoCerebro)._testar_modelo(modelo)

    def mudar_modelo_do_cerebro(self, agente: str, modelo: str) -> str:
        return servico(self, ServicoCerebro).mudar_modelo_do_cerebro(agente, modelo)

    def _chave_do_omniroute(self) -> str | None:
        return servico(self, ServicoCerebro)._chave_do_omniroute()

    def modelos_do_omniroute(self) -> list[str]:
        return servico(self, ServicoCerebro).modelos_do_omniroute()

    def configurar_omniroute(self, endereco: str, chave: str | None) -> str:
        return servico(self, ServicoCerebro).configurar_omniroute(endereco, chave)

    def testar_omniroute(self) -> tuple[bool, str]:
        return servico(self, ServicoCerebro).testar_omniroute()

    def modelos(self) -> dict[str, str]:
        return servico(self, ServicoCerebro).modelos()

    def baterias(self) -> dict[str, Bateria]:
        return servico(self, ServicoCerebro).baterias()

    def relatorio_de_baterias(self) -> str:
        return servico(self, ServicoCerebro).relatorio_de_baterias()

    def _fim_da_conversa(self) -> None:
        servico(self, ServicoCerebro)._fim_da_conversa()

    async def _revisar(self, turnos: list[dict[str, str]]) -> None:
        await servico(self, ServicoCerebro)._revisar(turnos)

    def _com_nucleo(self, texto: str) -> str:
        return servico(self, ServicoCerebro)._com_nucleo(texto)
