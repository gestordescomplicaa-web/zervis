"""Serviço de atendimento; pode ser exercitado com dependências próprias, sem subir o núcleo."""

import contextlib
import hashlib
import logging
import secrets
from typing import Any, Protocol

from zervis import atividade, fuso, usuario
from zervis.atendimento import agente, cliente, whatsapp
from zervis.avisos import caixa as caixa_mod
from zervis.avisos import falas_whatsapp, ligacoes, mensagens, pendentes
from zervis.avisos import modo as modo_fala
from zervis.cerebro import rapido
from zervis.nucleo import estados as e
from zervis.nucleo.apoio import DADOS

log = logging.getLogger(__name__)


class ContextoAtendimento(Protocol):
    avisos_lidos: Any
    caixa: Any
    central: Any
    cfg: Any
    eventos: Any
    leads: Any
    ligacao_pendente: Any
    maquina: Any
    mensagens: Any
    modo_fala: Any
    ponte_ligacao: Any
    prioridade: Any

    def _atendente_passou(self, nome: str, motivo: str) -> None: ...
    def _na_linha(self, tipo: str, texto: str) -> None: ...


class ServicoAtendimento:
    def __init__(self, contexto: ContextoAtendimento) -> None:
        self.n = contexto

    def _mensagem_importante(self, texto: str) -> None:
        self.n._na_linha("aviso", texto)
        if modo_fala.falar(self.n.modo_fala, "urgente"):
            self.n.eventos.put(e.Aviso(texto))

    # --- leads esperando resposta (ADR 0053) ---------------------------------------------------

    def _falar_lead(
        self, fala: str, contexto: str, pedido: bool = False, escutar: bool = False
    ) -> None:
        """A fala leva o texto do lead, inteira; o contexto do cérebro, só o nome: o texto é de
        terceiros e não entra na conversa como se fosse do Zé."""
        lidos = self.n.avisos_lidos
        lidos[fala] = contexto
        while len(lidos) > 20:
            del lidos[next(iter(lidos))]
        self.n.eventos.put(e.Aviso(fala, escutar=escutar, pedido=pedido))

    def _avisar_lead(self, fala: str, tela: str, contexto: str) -> None:
        if tela:
            self.n._na_linha("aviso", tela)  # a tela e a linha do tempo, só com o nome
        if modo_fala.falar(self.n.modo_fala, "urgente"):
            self._falar_lead(fala, contexto)
        self._leads_ao_celular()

    def _leads_ao_celular(self) -> None:
        """Os leads esperando resposta, inteiros, para o app de voz conectado: ele mostra uma
        notificação por lead, toca de novo no lembrete e apaga a que foi respondida."""
        fonte = getattr(self.n, "_fonte", None)
        if fonte is None or not getattr(fonte, "do_app", False):
            return
        leads = [pendentes.para_o_celular(p) for p in self.n.leads.abertas()]
        fonte.controle(tipo="whatsapp", leads=leads)

    def ouvir_lead(self, ident: str) -> None:
        """O "Ouvir" do celular: a mensagem inteira, falada mesmo no Silencioso (você pediu)."""
        p = self.n.leads.achar(ident)
        if p is not None:
            fala = pendentes.anuncio(p, usuario.PERFIL.nome)
            self._falar_lead(fala, f"Você pediu para ouvir a mensagem de {p.nome}.", pedido=True)

    def responder_whatsapp(self, chat: str, nome: str, texto: str) -> str:
        """A resposta ditada e já aprovada pela voz, direto na conversa (ADR 0054), pelo
        WhatsApp da Central. Bloqueia (rede): a ferramenta chama numa thread. A falha sobe como
        RuntimeError, com a frase da tela."""
        # Sem envio em dobro na mesma vez de responder: a chave muda quando ele escreve de novo.
        vez = self.n.caixa.ultima_dele(chat)
        chave = hashlib.sha256(f"{chat}:{vez}:{texto}".encode()).hexdigest()[:32]
        try:
            self.n.central.enviar(texto, chave, chat=chat)
        except cliente.CentralErro as erro:
            raise RuntimeError(f"Não enviei: {erro}") from erro
        self._lead_respondido(chat)  # a volta da mensagem pela Central também encerraria
        atividade.PADRAO.registrar("execucao", f"WhatsApp: resposta a {nome}", texto=texto)
        if (lista := getattr(self.n, "prioridade", None)) is None:
            return f"Enviado para {nome}."
        lista.esperar_resposta(nome, chat)  # o Zé escuta a resposta dela (ADR 0055)
        return f"Enviado para {nome}. Aviso quando responder."

    def iniciar_whatsapp(self, telefone: str, nome: str, texto: str) -> str:
        """Uma conversa nova, com quem nunca escreveu (o número de uma empresa que a pesquisa
        achou, por exemplo), já aprovada pela voz com o nome e o número (ADR 0061). O WaCalls
        confere se o número está no WhatsApp antes de enviar. Bloqueia; a falha sobe como
        RuntimeError, com a frase da tela."""
        chave = secrets.token_hex(16)  # cada "sim" é um envio; a chave só evita o envio em dobro
        try:
            self.n.central.enviar(texto, chave, telefone=telefone)
        except cliente.CentralErro as erro:
            raise RuntimeError(f"Não enviei: {erro}") from erro
        atividade.PADRAO.registrar("execucao", f"WhatsApp: conversa nova com {nome}", texto=texto)
        if (lista := getattr(self.n, "prioridade", None)) is None:
            return f"Enviado para {nome}."
        lista.esperar_resposta(nome, "", telefone)  # o Zé escuta a resposta (ADR 0055)
        return f"Enviado para {nome}. Aviso quando responder."

    def falar_whatsapp(self, nome: str, argumento: str) -> str:
        """As leituras do WhatsApp que o Zé responde sozinho, sem o cérebro (ADR 0056)."""
        local = fuso.local()
        calado = self.n.prioridade.calado
        if nome == "whatsapp_quem":
            return falas_whatsapp.quem(self.n.caixa, local, calado)
        if nome == "whatsapp_esperando":
            return falas_whatsapp.esperando(self.n.caixa, local, calado)
        if nome == "whatsapp_lista":
            return falas_whatsapp.lista(self.n.prioridade)
        return falas_whatsapp.ler(self.n.caixa, argumento, local)

    def agenda_whatsapp(self) -> list[dict[str, str]]:
        """Os contatos da agenda do celular (bloqueia: pergunta à Central); a falha sobe como
        RuntimeError, com a frase da tela."""
        try:
            lista: list[dict[str, str]] = self.n.central.agenda()
        except cliente.CentralErro as erro:
            raise RuntimeError(f"Não consegui ler a agenda: {erro}") from erro
        return lista

    def estado_whatsapp(self) -> dict[str, Any]:
        """Conectado ou não, e o número (bloqueia: pergunta à Central)."""
        tela: dict[str, Any] = self.n.central.para_tela()
        return tela

    def dispensar_lead(self, ident: str) -> str:
        """O "Já vi" (do celular ou pela voz): para de lembrar sem responder."""
        p = self.n.leads.dispensar(ident)
        if p is None:
            return "Nada esperando resposta com esse nome."
        atividade.PADRAO.registrar("execucao", f"WhatsApp: {p.nome} dispensado")
        self._leads_ao_celular()
        return f"Certo, não lembro mais de {p.nome}."

    def _lead_qualificado(
        self, nome: str, texto: str, telefone: str, chat: str, motivo: str = "lead"
    ) -> None:
        p = self.n.leads.novo(nome, texto, chat, telefone, motivo)
        titulo = pendentes.TITULOS.get(p.motivo, "Lead qualificado")
        atividade.PADRAO.registrar("execucao", f"WhatsApp: {titulo.lower()} ({p.nome})")
        self._avisar_lead(
            pendentes.anuncio(p, usuario.PERFIL.nome),
            pendentes.TELAS.get(p.motivo, pendentes.TELAS["lead"]).format(nome=p.nome),
            pendentes.CONTEXTOS.get(p.motivo, pendentes.CONTEXTOS["lead"]).format(nome=p.nome),
        )

    def _de_quem_vigio(self, nome: str, texto: str, telefone: str, chat: str, midia: str) -> bool:
        """Uma mensagem de quem está na lista de prioridade (ADR 0055): aviso na hora, lida, sem
        passar pelo julgamento de lead. Verdadeiro se era de alguém da lista."""
        lista = getattr(self.n, "prioridade", None)
        v = lista.chegou(chat, telefone) if lista is not None and chat else None
        if v is None:
            return False
        if v.motivo == "silencio":
            return True  # silenciado: só o arquivo
        lido = caixa_mod.descrever({"texto": texto, "midia": midia})
        if not self._continuar_lead(chat, lido):
            motivo = "resposta" if v.motivo == "resposta" else "prioridade"
            self._lead_qualificado(nome or v.nome, lido, telefone, chat, motivo)
        return True

    def _continuar_lead(self, chat: str, texto: str) -> bool:
        """O contato já espera resposta: a mensagem nova junta-se à pendência, sem julgar."""
        if self.n.leads.continuar(chat, texto) is None:
            return False
        self._leads_ao_celular()  # o texto novo aparece na notificação, sem tocar de novo
        return True

    def _lead_respondido(self, chat: str, quando: float = 0.0) -> None:
        if (p := self.n.leads.responder(chat, quando)) is not None:
            log.info("whatsapp: lead respondido")
            atividade.PADRAO.registrar("execucao", f"WhatsApp: {p.nome} respondido")
            self._leads_ao_celular()

    def _lembrar_leads(self) -> None:
        """A cada segundo, do laço: quem ainda espera resposta e já passou da hora de lembrar (o
        lead, quem está na lista de prioridade e quem respondeu ao que o Zé mandou). Com os avisos
        de lead desligados, o lead não é lembrado; os outros, sim."""
        ligados = self.n.mensagens.ativo
        vencidas = self.n.leads.vencidas(lambda p: ligados or p.motivo != "lead")
        if vencidas:
            nomes = pendentes.lista_falada([p.nome for p in vencidas])
            self._avisar_lead(
                pendentes.lembrete(vencidas, usuario.PERFIL.nome),
                "",
                f"Lembrete: {nomes} espera resposta no WhatsApp.",
            )

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
            nome, texto = str(evento.get("nome", "")), str(evento.get("texto", ""))
            telefone, chat = str(evento.get("telefone", "")), str(evento.get("chat", ""))
            midia, grupo = str(evento.get("midia", "")), bool(evento.get("grupo"))
            if (caixa := getattr(self.n, "caixa", None)) is not None:
                caixa.receber(
                    nome, texto, telefone, chat, midia, _hora(evento),
                    str(evento.get("evento", "")), grupo, str(evento.get("grupo_nome", "")),
                )  # fmt: skip
            if evento.get("repassado") or grupo:
                return  # o antigo e o grupo vão só para o arquivo: nada de aviso
            if self._de_quem_vigio(nome, texto, telefone, chat, midia):
                return
            leads = getattr(self.n, "leads", None)
            if leads is not None and leads.dispensada_ha_pouco(chat):
                return  # "já vi" há pouco: não vira lead de novo (nem gasta o julgamento)
            if texto:  # só o texto é julgado
                self.n.mensagens.receber(nome, texto, telefone, chat)
        elif evento.get("tipo") == "respondida":
            chat = str(evento.get("chat", ""))
            if (caixa := getattr(self.n, "caixa", None)) is not None:
                caixa.enviada(
                    chat, str(evento.get("texto", "")), str(evento.get("midia", "")),
                    _hora(evento), str(evento.get("evento", "")), bool(evento.get("grupo")),
                    str(evento.get("grupo_nome", "")), str(evento.get("nome", "")),
                )  # fmt: skip
            self._lead_respondido(chat, _quando(evento))
        elif evento.get("tipo") == "ligacao":
            self._ligacao_terminou(evento)
        elif evento.get("tipo") == "chamando":
            self._ligacao_chamando(evento)
        elif evento.get("tipo") == "ligacao_feita":
            self._ligacao_feita(evento)

    def _ligacao_terminou(self, evento: dict[str, Any]) -> None:
        """O agente atendeu uma ligação: o Zé guarda o que foi dito e avisa quem ligou, quanto
        durou e o resumo (antes, só que houve uma ligação: 06/11/2026)."""
        guardadas = getattr(self.n, "ligacoes", None)
        if guardadas is None:
            return
        lig = guardadas.registrar(evento)
        atividade.PADRAO.registrar(
            "execucao", f"Atendimento: ligação de {lig.quem}", origem="atendente",
            desfecho=lig.desfecho, duracao=lig.duracao,
        )  # fmt: skip
        if lig.desfecho == "falha" and not lig.conversa:
            return  # nem chegou a ser atendida: nada a contar
        if lig.desfecho == "transferida":
            self.n._na_linha("aviso", f"Ligação de {lig.quem}, atendida por você: {lig.resumo}")
            return  # você estava nela: fica guardada, sem aviso falado
        quem = agente.nome_falado(lig.nome) if lig.nome else lig.quem
        partes = [f"você recebeu uma ligação de {quem}, de {ligacoes.duracao_falada(lig.duracao)}."]
        if lig.desfecho == "passou":
            partes.append("A pessoa pediu para falar com você.")
        if lig.resumo:
            partes.append(modo_fala.para_ouvir(lig.resumo, limite=320))
        fala = pendentes.chamando(usuario.PERFIL.nome, " ".join(partes))
        self.n._na_linha("aviso", f"Ligação de {lig.quem}: {lig.resumo or 'sem resumo'}")
        if modo_fala.falar(
            self.n.modo_fala, "urgente" if lig.desfecho == "passou" else "notificacao"
        ):
            # O contexto do cérebro leva só quem e quando: o resumo vem do que o cliente disse.
            self._falar_lead(fala, f"Você avisou da ligação de {quem} (id {lig.id}).")

    # --- o Zé ligando para dar um recado seu (ADR 0067) -----------------------------------------

    def fazer_ligacao(self, telefone: str, nome: str, recado: str) -> str:
        """Pede à Central a ligação (já aprovada pela voz, ou agendada com a aprovação); o
        resultado chega depois, pelo evento "ligacao_feita"."""
        ident = secrets.token_hex(6)
        try:
            self.n.central.fazer_ligacao(ident, telefone, nome, recado)
        except cliente.CentralErro as erro:
            self._avisar_resultado(f"não consegui ligar para {nome or 'o contato'}: {erro}")
            raise RuntimeError(f"Não liguei: {erro}") from erro
        atividade.PADRAO.registrar("execucao", f"WhatsApp: ligando para {nome}", recado=recado)
        return f"Ligando para {nome}. Te aviso como foi."

    def _ligacao_feita(self, evento: dict[str, Any]) -> None:
        guardadas = getattr(self.n, "ligacoes", None)
        lig = guardadas.registrar(evento, "feita") if guardadas is not None else None
        nome = str(evento.get("nome", "")).strip()
        quem = agente.nome_falado(nome) if nome else _numero_dito(str(evento.get("telefone", "")))
        resultado, motivo = str(evento.get("resultado", "")), str(evento.get("motivo", ""))
        if resultado == "entregue":
            texto = f"liguei para {quem} e dei o seu recado."
            if resumo := str(evento.get("resumo", "")).strip():
                texto += " " + modo_fala.para_ouvir(resumo, limite=320)
        elif resultado == "nao_atendeu":
            texto = NAO_ATENDEU.get(motivo, "{quem} não atendeu.").format(quem=quem)
        else:
            texto = f"não consegui ligar para {quem}" + (f": {motivo}" if motivo else ".")
        atividade.PADRAO.registrar(
            "execucao", f"WhatsApp: ligação para {quem}", resultado=resultado, motivo=motivo,
            id=lig.id if lig else "",
        )  # fmt: skip
        self._avisar_resultado(texto)

    def _avisar_resultado(self, texto: str) -> None:
        texto = texto[:1].upper() + texto[1:] if texto else texto
        self.n._na_linha("aviso", texto)
        if modo_fala.falar(self.n.modo_fala, "notificacao"):
            self.n.eventos.put(e.Aviso(pendentes.chamando(usuario.PERFIL.nome, texto)))

    # --- chamar você durante a ligação (ADR 0066) -----------------------------------------------

    def _ligacao_chamando(self, evento: dict[str, Any]) -> None:
        """Alguém na linha pediu para falar com você: o Zé pergunta pelo app de voz e espera o
        "sim" (pela voz ou pelos botões da notificação). Sem o app conectado, não há por onde
        atender: o agente diz que você não pode agora e anota o recado."""
        chamada = str(evento.get("chamada", ""))
        nome, telefone = str(evento.get("nome", "")), str(evento.get("telefone", ""))
        quem = agente.nome_falado(nome) if nome else _numero_dito(telefone)
        assunto = " ".join(str(evento.get("assunto", "")).split())[:120] or "um assunto"
        fonte = getattr(self.n, "_fonte", None)
        if fonte is None or not getattr(fonte, "do_app", False):
            self.n._na_linha("aviso", f"{quem} ligou e queria falar com você: {assunto}.")
            with contextlib.suppress(cliente.CentralErro):
                self.n.central.decidir_ligacao(chamada, False)
            return
        self.n.ligacao_pendente = {"id": chamada, "quem": quem, "assunto": assunto}
        atividade.PADRAO.registrar(
            "execucao", f"Atendimento: {quem} quer falar com você", origem="atendente"
        )
        fonte.controle(tipo="ligacao", estado="chamando", id=chamada, nome=quem, assunto=assunto)
        fala = pendentes.chamando(
            usuario.PERFIL.nome,
            f"{quem} está na linha e quer falar com você sobre {assunto}. Pode atender?",
        )
        self.n._na_linha("aviso", f"{quem} está na linha e quer falar com você: {assunto}.")
        self._falar_lead(
            fala,
            f"Você perguntou se o usuário atende a ligação de {quem}, que espera na linha. "
            "Se ele disser que sim (atende, pode passar), use whatsapp_ligacao com atender; se "
            "disser que não, com recusar.",
            escutar=True,  # a resposta vem sem "Ei Zé", como no "Aprovo?"
        )

    def decidir_ligacao(self, atender: bool) -> str:
        """A sua resposta a quem espera na linha. Atendendo, a ligação vem para o app."""
        pendente = getattr(self.n, "ligacao_pendente", None)
        if not pendente:
            return "Nenhuma ligação esperando por você."
        self.n.ligacao_pendente = None
        fonte = getattr(self.n, "_fonte", None)
        atender = atender and fonte is not None and getattr(fonte, "do_app", False)
        try:
            url = self.n.central.decidir_ligacao(pendente["id"], atender)
        except cliente.CentralErro:
            return "A ligação já terminou."
        if not atender:
            self._ligacao_ao_celular(pendente["id"], "fim")
            quem = pendente["quem"]
            return f"Certo. O agente diz que você não pode agora e anota o recado de {quem}."
        from zervis.transporte.ponte import Ponte

        ponte = Ponte(url, self.n.central.token, fonte, self._ponte_fechou)
        try:
            ponte.iniciar()
        except Exception:
            log.exception("ponte: não abriu")
            with contextlib.suppress(cliente.CentralErro):
                self.n.central.encerrar_ligacao(pendente["id"])
            return "Não consegui passar a ligação para o celular."
        ponte.chamada = pendente["id"]
        self.n.ponte_ligacao = ponte
        self.n.maquina.em_ligacao = True  # os avisos esperam a ligação acabar
        self._ligacao_ao_celular(pendente["id"], "em_curso", pendente["quem"])
        atividade.PADRAO.registrar("execucao", f"Atendimento: você atendeu {pendente['quem']}")
        return f"Passando {pendente['quem']} para você."

    def encerrar_ligacao(self) -> str:
        ponte = getattr(self.n, "ponte_ligacao", None)
        if ponte is None:
            return "Nenhuma ligação em andamento."
        with contextlib.suppress(cliente.CentralErro):
            self.n.central.encerrar_ligacao(getattr(ponte, "chamada", ""))
        ponte.fechar()
        return "Ligação encerrada."

    def _ponte_fechou(self, ponte: Any) -> None:
        if getattr(self.n, "ponte_ligacao", None) is ponte:
            self.n.ponte_ligacao = None
        self.n.maquina.em_ligacao = False
        self._ligacao_ao_celular(getattr(ponte, "chamada", ""), "fim")

    def _ligacao_ao_celular(self, chamada: str, estado: str, quem: str = "") -> None:
        fonte = getattr(self.n, "_fonte", None)
        if fonte is not None and getattr(fonte, "do_app", False):
            fonte.controle(tipo="ligacao", estado=estado, id=chamada, nome=quem)

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
        if motivo.startswith("ligação"):
            return  # o fim da ligação avisa, com o resumo (`_ligacao_terminou`)
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


NAO_ATENDEU = {
    "declined": "{quem} recusou a ligação. O recado não foi dado.",
    "busy": "{quem} estava em outra ligação. O recado não foi dado.",
    "timeout": "{quem} não atendeu. O recado não foi dado.",
}


def _numero_dito(telefone: str) -> str:
    return f"o número {ligacoes.numero_falado(telefone)}" if telefone else "um número oculto"


def _quando(evento: dict[str, Any]) -> float:
    quando = evento.get("quando")
    return float(quando) if isinstance(quando, int | float) else 0.0


def _hora(evento: dict[str, Any]) -> float:
    """A hora da mensagem no WhatsApp; sem ela, a da chegada à Central."""
    hora = evento.get("hora")
    return float(hora) if isinstance(hora, int | float) and hora > 0 else _quando(evento)
