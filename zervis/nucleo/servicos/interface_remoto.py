"""Interface compatível do serviço de remoto."""

from typing import Any

from zervis.nucleo.servicos.interface import InterfaceServico, servico
from zervis.nucleo.servicos.remoto import ServicoRemoto
from zervis.transporte.websocket import Conexao


class InterfaceRemoto(InterfaceServico):
    def _no_proprio_pc(self) -> bool:
        return servico(self, ServicoRemoto)._no_proprio_pc()

    def _origem(self) -> str:
        return servico(self, ServicoRemoto)._origem()

    def _ligar_voz_remota(self) -> None:
        servico(self, ServicoRemoto)._ligar_voz_remota()

    def _fonte_remota(self, fonte: Any, conectada: bool) -> None:
        servico(self, ServicoRemoto)._fonte_remota(fonte, conectada)

    def _quadro_remoto(self, fonte: Any, quadro: bytes) -> None:
        servico(self, ServicoRemoto)._quadro_remoto(fonte, quadro)

    def voz_pelo_navegador(self, conexao: Conexao, taxa: int) -> None:
        servico(self, ServicoRemoto).voz_pelo_navegador(conexao, taxa)

    def estado_remoto(self) -> dict[str, Any]:
        return servico(self, ServicoRemoto).estado_remoto()

    def _aparelho_entrou(self, nome: str) -> None:
        servico(self, ServicoRemoto)._aparelho_entrou(nome)

    def _tunel_pronto(self, endereco: str) -> None:
        servico(self, ServicoRemoto)._tunel_pronto(endereco)

    def _tunel_caiu(self, endereco: str) -> None:
        servico(self, ServicoRemoto)._tunel_caiu(endereco)

    def _subir_tunel(self) -> None:
        servico(self, ServicoRemoto)._subir_tunel()

    def ativar_tunel(self) -> str:
        return servico(self, ServicoRemoto).ativar_tunel()

    def desativar_tunel(self) -> str:
        return servico(self, ServicoRemoto).desativar_tunel()

    def fixar_tunel(self, colado: str, digitado: str) -> str:
        return servico(self, ServicoRemoto).fixar_tunel(colado, digitado)

    def tunel_rapido(self) -> str:
        return servico(self, ServicoRemoto).tunel_rapido()

    def ativar_remoto(self) -> str:
        return servico(self, ServicoRemoto).ativar_remoto()

    def desativar_remoto(self) -> str:
        return servico(self, ServicoRemoto).desativar_remoto()

    def token_voz_remota(self) -> dict[str, str]:
        return servico(self, ServicoRemoto).token_voz_remota()
