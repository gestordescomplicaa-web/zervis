"""Ações da página voz."""

import logging
from typing import Any

from zervis import atividade
from zervis.avisos import modo as modo_fala
from zervis.nucleo import estados as e
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido
from zervis.presenca import modo as modo_escuta
from zervis.voz import chamado, deepgram, elevenlabs, espera

log = logging.getLogger(__name__)


class AcoesVoz(Pagina):
    dependencias = (
        "apertar",
        "aplicar_escuta",
        "deepgram",
        "eventos",
        "modelo_ativacao",
        "motor_voz",
        "mudar_chamado",
        "mudar_escuta",
        "mudar_espera",
        "mudar_modo_fala",
        "soltar",
        "token_voz_remota",
    )

    def mudar_modo_fala(self, dados: dict[str, Any]) -> dict[str, Any]:
        modo = str(dados.get("modo", ""))
        if modo not in modo_fala.MODOS:
            raise PedidoInvalido("modo de fala desconhecido")
        return {"modo": modo, "aviso": self.n.mudar_modo_fala(modo)}

    def mudar_escuta(self, dados: dict[str, Any]) -> dict[str, Any]:
        modo = str(dados.get("modo", ""))
        if modo not in modo_escuta.MODOS:
            raise PedidoInvalido("modo de escuta desconhecido")
        try:
            aviso = self.n.mudar_escuta(modo)
        except ValueError as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {"modo": modo, "aviso": aviso}

    def evento_voz(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O que aconteceu na voz do navegador (conectou, caiu, erro de microfone): só para o
        registro, para diagnosticar o celular; nunca áudio nem credenciais."""
        evento = str(dados.get("evento", ""))[:40]
        detalhe = " ".join(str(dados.get("detalhe", "")).split())[:300]
        aparelho = str(dados.get("aparelho", ""))[:120]
        nivel = logging.INFO if evento in ("conectou", "desligou", "encerrada") else logging.WARNING
        log.log(nivel, "voz do navegador: %s %s (%s)", evento, detalhe, aparelho)
        if evento in ("falhou", "microfone"):
            atividade.PADRAO.registrar(
                "falha", "A voz do navegador falhou", erro=detalhe, aparelho=aparelho
            )
        return {}

    def apertar(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Botão de falar apertado: abre o pedido, como o "Ei Zé"."""
        try:
            self.n.apertar()
        except ValueError as erro:
            raise PedidoInvalido(str(erro)) from None
        return {}

    def soltar(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.n.soltar()
        return {}

    def mudar_chamado(self, dados: dict[str, Any]) -> dict[str, Any]:
        modo = str(dados.get("modo", ""))
        if modo not in chamado.MODOS:
            raise PedidoInvalido("ativação desconhecida")
        return {"modo": modo, "aviso": self.n.mudar_chamado(modo)}

    def mudar_espera(self, dados: dict[str, Any]) -> dict[str, Any]:
        modo = str(dados.get("modo", ""))
        if modo not in espera.MODOS:
            raise PedidoInvalido("espera desconhecida")
        return {"modo": modo, "aviso": self.n.mudar_espera(modo)}

    def token_voz(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Entrar na sala da voz remota pelo navegador (token curto, só microfone)."""
        try:
            return dict(self.n.token_voz_remota())
        except ValueError as erro:
            raise PedidoInvalido(str(erro)) from erro

    def escuta(self) -> dict[str, Any]:
        dg = self.n.deepgram
        ativacao = getattr(self.n.modelo_ativacao, "treinada", True)
        return {"deepgram": dg.situacao(), "cadastro": deepgram.CADASTRO, "ativacao": ativacao}

    def guardar_chave_escuta(self, dados: dict[str, Any]) -> dict[str, Any]:
        chave = str(dados.get("chave", "")).strip()
        try:
            deepgram.gravar_chave(self.n.deepgram.arquivo_chave, chave)
        except ValueError as erro:
            raise PedidoInvalido(str(erro)) from None
        self.n.aplicar_escuta()
        ok, mensagem = deepgram.conferir(chave)
        aviso = "Chave salva." if ok else f"Chave salva. {mensagem}"
        return {**self.painel.escuta(), "aviso": aviso, "valida": ok}

    def apagar_chave_escuta(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.n.deepgram.arquivo_chave.unlink(missing_ok=True)
        self.n.aplicar_escuta()
        return {**self.painel.escuta(), "aviso": "Chave removida."}

    def testar_chave_escuta(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Confere a chave colada (ou, sem ela, a guardada) direto no Deepgram."""
        chave = str(dados.get("chave", "")).strip() or (self.n.deepgram.chave or "")
        if not chave:
            return {"ok": False, "mensagem": "Informe a chave."}
        ok, mensagem = deepgram.conferir(chave)
        return {"ok": ok, "mensagem": mensagem}

    # --- quem fala: o Cadu ou o ElevenLabs (ADR 0041) -------------------------------------------

    def sintese(self) -> dict[str, Any]:
        motor = self.n.motor_voz
        erro = ""
        if motor.chave and not motor.vozes:
            try:
                motor.vozes = elevenlabs.vozes(motor.chave, motor.endereco)
            except elevenlabs.ErroVoz as falha:
                erro = str(falha)
        situacao = motor.situacao()
        return {
            **situacao,
            "erro": situacao["erro"] or erro,
            "vozes": motor.vozes,
            "cadastro": elevenlabs.CADASTRO,
        }

    def _usar(self, escolha: elevenlabs.Escolha) -> None:
        motor = self.n.motor_voz
        elevenlabs.gravar_escolha(escolha, motor.arquivo_escolha)
        motor.recarregar()
        log.info("voz: %s %s", escolha.motor, escolha.nome)
        # Ouvir na hora como ficou. Como aviso, ela respeita o Silencioso e espera a pessoa
        # terminar de falar; o nome no texto evita que a regra de não repetir a cale.
        self.n.eventos.put(e.Aviso(elevenlabs.amostra(escolha)))

    def guardar_chave_sintese(self, dados: dict[str, Any]) -> dict[str, Any]:
        """A chave colada: confere listando as vozes e já passa a falar pelo ElevenLabs."""
        motor = self.n.motor_voz
        try:
            motor.vozes = elevenlabs.guardar_chave(motor, str(dados.get("chave", "")))
        except elevenlabs.ErroVoz as erro:
            raise PedidoInvalido(str(erro)) from None
        atual = motor.escolha
        voz = next((v for v in motor.vozes if v["id"] == atual.voz), motor.vozes[0])
        self._usar(elevenlabs.Escolha("elevenlabs", voz["id"], voz["nome"]))
        return {**self.painel.sintese(), "aviso": f"Chave salva. Voz: {voz['nome']}."}

    def apagar_chave_sintese(self, dados: dict[str, Any]) -> dict[str, Any]:
        motor = self.n.motor_voz
        motor.arquivo_chave.unlink(missing_ok=True)
        motor.vozes = []
        elevenlabs.gravar_escolha(elevenlabs.Escolha(), motor.arquivo_escolha)
        motor.recarregar()
        return {**self.painel.sintese(), "aviso": "Chave removida. O Cadu volta a falar."}

    def escolher_sintese(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Cadu ou ElevenLabs, e qual voz; o Zé fala uma frase com a escolha."""
        motor = self.n.motor_voz
        nome_motor = str(dados.get("motor", ""))
        if nome_motor not in elevenlabs.MOTORES:
            raise PedidoInvalido("motor de voz desconhecido")
        if nome_motor == "piper":
            atual = motor.escolha
            self._usar(elevenlabs.Escolha("piper", atual.voz, atual.nome))
            return {**self.painel.sintese(), "aviso": "Voz: Cadu."}
        if not motor.chave:
            raise PedidoInvalido("Cole a chave do ElevenLabs primeiro.")
        pedida = str(dados.get("voz", "")) or motor.escolha.voz
        voz = next((v for v in motor.vozes if v["id"] == pedida), None)
        if voz is None:
            raise PedidoInvalido("Voz desconhecida. Atualize a lista.")
        self._usar(elevenlabs.Escolha("elevenlabs", voz["id"], voz["nome"]))
        return {**self.painel.sintese(), "aviso": f"Voz: {voz['nome']}."}
