"""Ações da página voz."""

import logging
from typing import Any

from zervis import atividade
from zervis.avisos import modo as modo_fala
from zervis.nucleo import estados as e
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido
from zervis.presenca import modo as modo_escuta
from zervis.voz import chamado, deepgram, espera, nuvem

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

    # --- quem fala: o Cadu, o ElevenLabs ou o Fish Audio (ADR 0041) ----------------------------

    def _provedor(self, dados: dict[str, Any]) -> tuple[Any, str, Any]:
        motor = self.n.motor_voz
        nome = str(dados.get("provedor", ""))
        if nome not in motor.provedores:
            raise PedidoInvalido("provedor de voz desconhecido")
        return motor, nome, motor.provedores[nome]

    def sintese(self) -> dict[str, Any]:
        """Quem fala, e de cada provedor com chave: as vozes e o que se sabe da conta."""
        motor = self.n.motor_voz
        situacao = motor.situacao()
        erros = []
        for nome, p in motor.provedores.items():
            chave = motor.chaves.get(nome)
            if chave and (nome not in motor.vozes or nome not in motor.contas):
                try:  # uma vez por subida do Zé; guardar a chave de novo atualiza
                    motor.contas[nome] = p.conta(chave, motor.enderecos[nome])[1]
                    motor.vozes[nome] = p.vozes(chave, motor.enderecos[nome])
                except nuvem.ErroVoz as falha:
                    erros.append(f"{p.TITULO}: {falha}")
            dados = situacao["provedores"][nome]
            dados["vozes"] = motor.vozes.get(nome, []) if chave else []
            dados["conta"] = motor.contas.get(nome, "") if chave else ""
        return {**situacao, "erro": situacao["erro"] or " ".join(erros)}

    def _usar(self, escolha: nuvem.Escolha) -> None:
        motor = self.n.motor_voz
        motor.gravar(escolha)
        provedor = motor.ativo
        nome = escolha.voz(provedor).get("nome", "") if provedor else "do Cadu"
        log.info("voz: %s %s", escolha.motor, nome)
        # Ouvir na hora como ficou. Como aviso, ela respeita o Silencioso e espera a pessoa
        # terminar de falar.
        self.n.eventos.put(e.Aviso(nuvem.amostra(motor.titulo(escolha.motor), nome)))

    def guardar_chave_sintese(self, dados: dict[str, Any]) -> dict[str, Any]:
        """A chave colada: confere no provedor e já passa a falar por ele."""
        motor, nome, p = self._provedor(dados)
        endereco = motor.enderecos[nome]
        try:
            chave = nuvem.validar_chave(str(dados.get("chave", "")))
            modelo, nota = p.conta(chave, endereco)
            lista = p.vozes(chave, endereco)
        except nuvem.ErroVoz as erro:
            raise PedidoInvalido(str(erro)) from None
        if not lista:
            raise PedidoInvalido("A conta não tem nenhuma voz.")
        nuvem.guardar_chave(motor, nome, chave)
        motor.vozes[nome], motor.contas[nome] = lista, nota
        atual = motor.escolha.voz(nome)
        voz = next((v for v in lista if v["id"] == atual.get("id")), None)
        voz = voz or ({**atual} if atual.get("id") else lista[0])  # uma colada antes continua
        self._usar(motor.escolha.com_voz(nome, {**voz, "modelo": modelo}))
        return {**self.painel.sintese(), "aviso": f"Chave salva. Voz: {voz['nome']}."}

    def apagar_chave_sintese(self, dados: dict[str, Any]) -> dict[str, Any]:
        motor, nome, _ = self._provedor(dados)
        motor.arquivo_chave(nome).unlink(missing_ok=True)
        motor.vozes.pop(nome, None)
        motor.contas.pop(nome, None)
        escolha = motor.escolha
        if escolha.motor == nome:
            escolha = nuvem.Escolha(nuvem.LOCAL, escolha.vozes)
        motor.gravar(escolha)
        aviso = "Chave removida." + (" O Cadu volta a falar." if motor.ativo is None else "")
        return {**self.painel.sintese(), "aviso": aviso}

    def escolher_sintese(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O Cadu ou um provedor, e qual voz (da lista ou um link colado); o Zé fala uma frase
        com a escolha."""
        motor = self.n.motor_voz
        nome = str(dados.get("motor", ""))
        if nome == nuvem.LOCAL:
            self._usar(nuvem.Escolha(nuvem.LOCAL, motor.escolha.vozes))
            return {**self.painel.sintese(), "aviso": "Voz: Cadu."}
        motor, nome, p = self._provedor({"provedor": nome})
        chave = motor.chaves.get(nome)
        if not chave:
            raise PedidoInvalido(f"Cole a chave do {p.TITULO} primeiro.")
        atual = motor.escolha.voz(nome)
        pedida = str(dados.get("voz", "")).strip() or atual.get("id", "")
        voz = next((v for v in motor.vozes.get(nome, []) if v["id"] == pedida), None)
        if voz is None and pedida == atual.get("id"):
            voz = atual
        if voz is None:
            try:
                voz = p.voz_colada(pedida, chave, motor.enderecos[nome])
            except nuvem.ErroVoz as erro:
                raise PedidoInvalido(str(erro)) from None
        if voz is None:
            raise PedidoInvalido("Voz desconhecida. Escolha na lista ou cole o link da voz.")
        modelo = atual.get("modelo", "")
        self._usar(motor.escolha.com_voz(nome, {**voz, "modelo": modelo}))
        return {**self.painel.sintese(), "aviso": f"Voz: {voz['nome']}."}
