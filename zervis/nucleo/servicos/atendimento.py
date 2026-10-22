"""Serviço de atendimento; pode ser exercitado com dependências próprias, sem subir o núcleo."""

import contextlib
import logging
from typing import Any, Protocol

from zervis import atividade
from zervis.atendimento import agente, cliente, whatsapp
from zervis.avisos import mensagens
from zervis.avisos import modo as modo_fala
from zervis.cerebro import rapido
from zervis.nucleo import estados as e
from zervis.nucleo.apoio import DADOS

log = logging.getLogger(__name__)


class ContextoAtendimento(Protocol):
    central: Any
    cfg: Any
    eventos: Any
    mensagens: Any
    modo_fala: Any

    def _atendente_passou(self, nome: str, motivo: str) -> None: ...
    def _na_linha(self, tipo: str, texto: str) -> None: ...


class ServicoAtendimento:
    def __init__(self, contexto: ContextoAtendimento) -> None:
        self.n = contexto

    def _mensagem_importante(self, texto: str) -> None:
        self.n._na_linha("aviso", texto)
        if modo_fala.falar(self.n.modo_fala, "urgente"):
            self.n.eventos.put(e.Aviso(texto))

    def _motor_das_mensagens(self) -> rapido.Motor:
        """O motor da via rápida, se ligado; senão o Claude da assinatura, sem ferramentas."""
        via = rapido.efetiva(self.n.cfg["via_rapida"])
        if via["ligada"]:
            with contextlib.suppress(rapido.MotorErro):
                if (motor := rapido.criar_motor(via, DADOS / "mensagens")) is not None:
                    return motor
        return rapido.MotorPlano("haiku", DADOS / "mensagens")

    def _evento_da_central(self, evento: dict[str, Any]) -> None:
        if evento.get("tipo") == "passou":
            self.n._atendente_passou(str(evento.get("nome", "")), str(evento.get("motivo", "")))
        elif evento.get("tipo") == "mensagem":
            self.n.mensagens.receber(str(evento.get("nome", "")), str(evento.get("texto", "")))
        elif evento.get("tipo") == "ligacao":
            telefone = str(evento.get("telefone", "")) or "número oculto"
            atividade.PADRAO.registrar(
                "execucao", f"Atendimento: ligação de +{telefone}", origem="atendente",
                desfecho=str(evento.get("desfecho", "")),
            )  # fmt: skip

    def _motor_do_atendente(self) -> rapido.Motor:
        """Um modelo sem ferramentas para cada resposta do agente de atendimento."""
        from zervis.atendimento import cerebro

        motor: rapido.Motor = cerebro.criar(agente.ler().cerebro, DADOS / "atendente-modelo")
        return motor

    def _atendente_passou(self, nome: str, motivo: str) -> None:
        """O agente passou uma conversa para quem usa. A fala tem só o nome; o motivo (escrito
        pelo modelo a partir do cliente) fica na tela."""
        atividade.PADRAO.registrar(
            "execucao", f"Atendimento: {nome} passou para você", origem="atendente", motivo=motivo
        )
        self.n._na_linha("aviso", f"{nome}, no WhatsApp, precisa de você: {motivo}")
        if modo_fala.falar(self.n.modo_fala, "urgente"):
            self.n.eventos.put(
                e.Aviso(f"{agente.nome_falado(nome)}, no WhatsApp, precisa de você.")
            )

    def _subir_central(self) -> None:
        try:
            self.n.central.garantir()
        except cliente.CentralErro as erro:
            log.warning("central de atendimento não subiu: %s", erro)
        self.n.central.iniciar_eventos()

    def conectar_whatsapp(self) -> str:
        """Sobe a Central e pede o QR. Na primeira vez a Central compila o WaCalls, o que leva
        alguns minutos; a tela acompanha pelo estado."""
        if whatsapp.go() is None and whatsapp.binario() is None:
            raise whatsapp.WhatsAppErro("Go não encontrado.")
        try:
            self.n.central.conectar()
        except cliente.CentralErro as erro:
            raise whatsapp.WhatsAppErro(str(erro)) from erro
        atividade.PADRAO.registrar("execucao", "WhatsApp: pareamento iniciado", origem="painel")
        return "Conectando o WhatsApp."

    def desconectar_whatsapp(self) -> str:
        try:
            self.n.central.desconectar()
        except cliente.CentralErro as erro:
            raise whatsapp.WhatsAppErro(str(erro)) from erro
        atividade.PADRAO.registrar("execucao", "WhatsApp desconectado", origem="painel")
        return "WhatsApp desconectado."

    def ligar_mensagens(self, ativo: bool) -> str:
        """Avisos de lead quente no WhatsApp (painel e voz)."""
        if ativo and not (mensagens.disponivel() or self.n.central.whatsapp_ativo):
            return "Avisos do WhatsApp indisponíveis neste sistema."
        mensagens.escolher(ativo)
        if ativo:
            self.n.mensagens.iniciar()
            return "Avisos do WhatsApp ligados."
        self.n.mensagens.parar()
        return "Avisos do WhatsApp desligados."
