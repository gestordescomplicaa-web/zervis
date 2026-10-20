"""Ações da página acesso."""

import logging
from typing import Any

import segno

from zervis import usuario
from zervis.portal import remoto
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.senha import SenhaErro
from zervis.portal.servidor import PedidoInvalido

log = logging.getLogger(__name__)


class AcoesAcesso(Pagina):
    dependencias = (
        "acesso",
        "ativar_remoto",
        "ativar_tunel",
        "desativar_remoto",
        "desativar_tunel",
        "estado_remoto",
        "tunel",
    )

    def remoto(self) -> dict[str, Any]:
        return dict(self.n.estado_remoto())

    def ativar_remoto(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            aviso = self.n.ativar_remoto()
        except remoto.RemotoErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.painel.remoto(), "aviso": aviso}

    def ativar_tunel(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            aviso = self.n.ativar_tunel()
        except remoto.RemotoErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.painel.remoto(), "aviso": aviso}

    def desativar_tunel(self, dados: dict[str, Any]) -> dict[str, Any]:
        return {**self.painel.remoto(), "aviso": self.n.desativar_tunel()}

    def desativar_remoto(self, dados: dict[str, Any]) -> dict[str, Any]:
        return {**self.painel.remoto(), "aviso": self.n.desativar_remoto()}

    def definir_senha(self, dados: dict[str, Any]) -> dict[str, Any]:
        """A senha de quem entra de outro aparelho; trocá-la encerra os acessos."""
        try:
            self.n.acesso.definir(str(dados.get("senha", "")))
        except SenhaErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.painel.remoto(), "aviso": "Senha salva."}

    def desconectar_aparelho(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            self.n.acesso.desconectar_por_id(str(dados.get("id", "")))
        except SenhaErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.painel.remoto(), "aviso": "Aparelho desconectado."}

    def preparar_codigo(self, dados: dict[str, Any]) -> dict[str, Any]:
        """A semente nova do autenticador: QR para ler e a chave para digitar."""
        endereco = self.n.acesso.preparar_codigo(usuario.PERFIL.nome)
        qr = segno.make(endereco, error="m").svg_inline(
            scale=4, dark="#070c11", light="#ffffff", border=2
        )
        chave = self.n.acesso.semente_pendente
        return {"qr": qr, "chave": " ".join(chave[i : i + 4] for i in range(0, len(chave), 4))}

    def confirmar_codigo(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            self.n.acesso.confirmar_codigo(str(dados.get("codigo", "")))
        except SenhaErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.painel.remoto(), "aviso": "Verificação em duas etapas ligada."}

    def desligar_codigo(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.n.acesso.desligar_codigo()
        if self.n.tunel.ativo:
            self.n.desativar_tunel()  # na internet aberta, só com o código
        return {**self.painel.remoto(), "aviso": "Verificação em duas etapas desligada."}

    def encerrar_acessos(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.n.acesso.sair_todos()
        return {**self.painel.remoto(), "aviso": "Acessos encerrados."}
