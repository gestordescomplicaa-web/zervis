"""Ações da página atendimento."""

import contextlib
import logging
from pathlib import Path
from typing import Any

import segno

from zervis import atividade
from zervis.atendimento import agente, cliente, ligacao, projeto, whatsapp
from zervis.atendimento import cerebro as cerebro_do_agente
from zervis.cerebro import rapido
from zervis.portal.acoes.apoio import _ler
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido

log = logging.getLogger(__name__)


class AcoesAtendimento(Pagina):
    dependencias = (
        "_motor_do_atendente",
        "central",
        "conectar_whatsapp",
        "deepgram",
        "desconectar_whatsapp",
        "ligar_mensagens",
        "mensagens",
        "projeto_agente",
        "sessoes",
        "testes_do_atendente",
    )

    def mudar_mensagens(self, dados: dict[str, Any]) -> dict[str, Any]:
        aviso = self.n.ligar_mensagens(bool(dados.get("ligar")))
        return {"ligado": self.n.mensagens.ativo, "aviso": aviso}

    def atendimento(self) -> dict[str, Any]:
        tela = self.n.central.para_tela()
        if qr := tela.pop("qr", ""):
            tela["qr"] = segno.make(qr, error="l").svg_inline(
                scale=4, dark="#070c11", light="#ffffff", border=2
            )
        raiz = self.n.projeto_agente
        try:
            p, erro = projeto.rascunho(raiz), ""
        except agente.AgenteErro as falha:
            p, erro = projeto.perfil(), str(falha)
        publicado = agente.PASTA / "publicado"
        return {
            "whatsapp": tela,
            "avisos": {"ligado": self.n.mensagens.ativo},
            "agente": {
                "nome": p.nome,
                "empresa": p.empresa,
                "persona": p.persona,
                "conhecimento": _ler(raiz / "conhecimento" / "geral.md") if projeto.existe(raiz)
                else p.conhecimento,
                "outros_arquivos": projeto.conhecimento_extra(raiz),
                "passar": p.passar,
                "passar_padrao": agente.PASSAR_PADRAO,
                "ligado": p.ligado,
                "modo": p.modo,
                "numeros_teste": p.numeros_teste,
                "ligacoes": p.ligacoes,
                "cerebro": {
                    "atual": f"{p.cerebro['motor']}|{p.cerebro['modelo']}",
                    "nome": cerebro_do_agente.nome(p.cerebro),
                    "rapido": cerebro_do_agente.rapido_nas_ligacoes(p.cerebro),
                    "opcoes": cerebro_do_agente.opcoes(),
                },
                "ligacoes_falta": self.painel._falta_para_ligacoes(),
                "pasta": str(raiz),
                "criado": projeto.existe(raiz),
                "publicado": projeto.existe(publicado),
                "pendente": projeto.pendente(raiz, publicado),
                "erro": erro,
            },
            "pausados": self.n.central.pausados(),
            "chaves": cerebro_do_agente.chaves(),
            "memoria": agente.Registros(agente.PASTA).memoria(),
        }  # fmt: skip

    def salvar_atendente(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O formulário: a persona vai para o rascunho (a pasta); os ajustes valem na hora."""
        raiz = self.n.projeto_agente
        persona = {k: dados[k] for k in agente.LIMITES if k in dados}
        ajustes = {k: dados[k] for k in agente.AJUSTES if k in dados}
        try:
            if persona:
                projeto.gravar(raiz, persona)
            p = agente.validar(ajustes, agente.ler())
        except agente.AgenteErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        if p.ligado and p.modo == "teste" and not p.numeros_teste:
            raise PedidoInvalido("Informe ao menos um número de teste.")
        if p.ligado and not projeto.existe(agente.PASTA / "publicado"):
            raise PedidoInvalido("Publique o agente antes de ligar.")
        if (
            p.ligacoes
            and not agente.ler().ligacoes
            and (falta := self.painel._falta_para_ligacoes())
        ):
            raise PedidoInvalido(falta)
        agente.gravar(p)
        atividade.PADRAO.registrar(
            "execucao",
            "Agente de atendimento salvo",
            origem="painel",
            estado=("ligado" if p.ligado else "desligado") + f", modo {p.modo}",
        )
        return {**self.painel.atendimento(), "aviso": "Agente salvo."}

    def _falta_para_ligacoes(self) -> str:
        if not self.n.deepgram.disponivel:
            return "Configure a chave do Deepgram na página Voz."
        if not ligacao.voz_pronta():
            return "A voz do Zé ainda não foi baixada."
        return ""

    def publicar_atendente(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Roda os testes de conversa do rascunho e, se todos passarem, publica."""
        try:
            r = projeto.publicar(
                self.n.projeto_agente,
                agente.PASTA,
                self.n._motor_do_atendente,
                self.n.testes_do_atendente.executar,
            )
        except agente.AgenteErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        if r["publicado"]:
            atividade.PADRAO.registrar(
                "execucao", "Agente de atendimento publicado", origem="painel",
                testes=len(r["resultados"]),
            )  # fmt: skip
        return {**self.painel.atendimento(), **r}

    def sessao_do_atendente(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Uma sessão de código na pasta do agente (a mesma, se já houver uma)."""
        raiz = self.n.projeto_agente
        try:
            projeto.criar(raiz)
        except OSError as erro:
            raise PedidoInvalido("Não foi possível criar a pasta do agente.") from erro
        pasta = str(raiz.resolve())
        for s in self.n.sessoes.listar():
            if str(Path(s.pasta).resolve()) == pasta:
                return self.painel._sessao(s)
        s = self.painel._chamar(lambda: self.n.sessoes.criar("Agente de atendimento", pasta))
        return self.painel._sessao(s)

    def testar_atendente(self, dados: dict[str, Any]) -> dict[str, Any]:
        texto = str(dados.get("texto", "")).strip()[:2000]
        if not texto:
            raise PedidoInvalido("Escreva uma mensagem.")
        historico = dados.get("historico")
        turnos = [
            {"quem": str(t.get("quem", "")), "texto": str(t.get("texto", ""))[:2000]}
            for t in (historico if isinstance(historico, list) else [])[-agente.TURNOS :]
            if isinstance(t, dict)
        ]
        try:
            return agente.simular(
                self.n.testes_do_atendente.executar,
                self.n._motor_do_atendente(),
                projeto.rascunho(self.n.projeto_agente),
                turnos,
                texto,
            )
        except Exception as erro:
            log.warning("atendente: teste sem resposta (%s)", type(erro).__name__)
            raise PedidoInvalido("Sem resposta do modelo.") from erro

    def esquecer_atendimento(self, dados: dict[str, Any]) -> dict[str, Any]:
        if dados.get("confirmado") is not True:
            raise PedidoInvalido("confirmação necessária")
        n = agente.Registros(agente.PASTA).esquecer()
        atividade.PADRAO.registrar("execucao", "Memória do atendimento apagada", origem="painel",
                                   contatos=n)  # fmt: skip
        return {**self.painel.atendimento(), "aviso": "Memória apagada."}

    def chave_do_atendente(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Guarda a chave de API (a mesma da via rápida) e confere com uma resposta curta."""
        motor, chave = str(dados.get("motor", "")), str(dados.get("chave", "")).strip()
        if motor not in cerebro_do_agente.API:
            raise PedidoInvalido("Serviço desconhecido.")
        if chave:
            try:
                rapido.gravar_chave(motor, chave)
            except rapido.MotorErro as erro:
                raise PedidoInvalido("Chave inválida.") from erro
        if not cerebro_do_agente.tem_chave(motor):
            raise PedidoInvalido("Informe a chave.")
        ok = self.painel._testar_cerebro(
            {"motor": motor, "modelo": cerebro_do_agente.API[motor][0][0]}
        )
        aviso = "Chave válida." if ok else "Chave salva, mas o serviço não respondeu."
        return {**self.painel.atendimento(), "aviso": aviso, "valida": ok}

    def apagar_chave_do_atendente(self, dados: dict[str, Any]) -> dict[str, Any]:
        motor = str(dados.get("motor", ""))
        if motor not in cerebro_do_agente.API:
            raise PedidoInvalido("Serviço desconhecido.")
        rapido.apagar_chave(motor)
        p = agente.ler()
        if p.cerebro.get("motor") == motor:  # sem a chave, o agente volta ao padrão
            agente.gravar(agente.validar({"cerebro": dict(cerebro_do_agente.PADRAO)}, p))
        return {**self.painel.atendimento(), "aviso": "Chave removida."}

    def _testar_cerebro(self, escolha: dict[str, str]) -> bool:
        async def uma() -> bool:
            motor = cerebro_do_agente.criar(escolha, self.painel.pasta_teste / "atendente")
            try:
                await motor.iniciar("Responda só: ok")
                pedido = [{"role": "user", "content": "ok?"}]
                partes = [p async for p in motor.gerar("Responda só: ok", pedido)]
                return bool("".join(partes).strip())
            finally:
                with contextlib.suppress(Exception):
                    await motor.fechar()

        try:
            return bool(self.n.testes_do_atendente.executar(uma(), 30))
        except Exception:
            return False

    def devolver_atendimento(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            self.n.central.devolver(str(dados.get("telefone", "")))
        except cliente.CentralErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.painel.atendimento(), "aviso": "Conversa devolvida ao agente."}

    def conectar_whatsapp(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            aviso = self.n.conectar_whatsapp()
        except whatsapp.WhatsAppErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.painel.atendimento(), "aviso": aviso}

    def desconectar_whatsapp(self, dados: dict[str, Any]) -> dict[str, Any]:
        if dados.get("confirmado") is not True:
            raise PedidoInvalido("confirmação necessária")
        try:
            aviso = self.n.desconectar_whatsapp()
        except whatsapp.WhatsAppErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.painel.atendimento(), "aviso": aviso}
