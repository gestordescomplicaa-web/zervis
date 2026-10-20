"""Ações da página voz."""

import logging
from typing import Any

from zervis import atividade
from zervis.avisos import modo as modo_fala
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido
from zervis.presenca import modo as modo_escuta
from zervis.voz import chamado, deepgram, espera

log = logging.getLogger(__name__)


class AcoesVoz(Pagina):
    dependencias = (
        "apertar",
        "aplicar_escuta",
        "deepgram",
        "modelo_ativacao",
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
