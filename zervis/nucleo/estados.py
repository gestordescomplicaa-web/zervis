"""Máquina de estados do núcleo (docs/04-arquitetura.md).

Pura: recebe eventos e devolve efeitos; quem toca microfone, voz, cérebro e anel é o laço.
Assim as cinco invariantes viram testes diretos:
  1. Em INATIVO o microfone está fechado e nenhuma voz sai.
  2. Só se entra em OUVINDO pela ativação ou pela continuação da conversa que ela abriu;
     cada pedido consome uma autorização e só a resposta a ele concede a próxima.
     "ok" ou o silêncio encerram a conversa (ADR 0009).
  3. Em FALANDO nada é transcrito (eco); só o detector de ativação escuta, para interromper.
  4. CONFIRMANDO só aprova com "sim"; qualquer outra coisa, silêncio ou mais de 40 s nega.
  5. Uma fala por vez; avisos só saem em ATIVO, sem pedido em andamento.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from zervis.nucleo.comandos import (
    _DE,
    _NAO_E_NOME,
    _WA,
    BRILHO_SEM_ALVO,
    COMANDOS,
    FALAS_DAS_AREAS,
    MANUTENCAO_APOIO,
    MANUTENCAO_DESLIGAR,
    MANUTENCAO_LIGAR,
    ORBE_ARTIGOS,
    ORBE_DENTRO,
    ORBE_TIPOS,
    ORBE_VERBOS,
    ORBES_PADRAO,
    TROCAR_APOIO,
    TROCAR_NOMES,
    TROCAR_VERBOS,
    WHATSAPP_LOCAL,
    _parece_manutencao,
    comando,
    manutencao,
    orbe,
    resposta_a_permissao,
    troca,
    whatsapp_local,
)
from zervis.nucleo.entender import (
    APROVA,
    APROVA_NO_COMECO,
    CHAMADOS,
    CONCORDANCIAS,
    CORRIGE,
    ENCERRAR_APOIO,
    ENCERRAR_PRINCIPAIS,
    INTERROMPER,
    NAO_ENTENDI,
    NEGA,
    NOMES,
    OFERTA,
    REPERGUNTA,
    RESPOSTA_CURTA,
    TUDO,
    VACILOS,
    encerra,
    entender_resposta,
    palavras,
    pedido_valido,
    resposta_a_oferta,
    sem_chamado,
    sem_nome,
    so_concordancia,
)
from zervis.nucleo.voz_tipos import (
    AbrirMicrofone,
    AoVivo,
    Apertou,
    AprovacaoExpirou,
    Ativacao,
    Aviso,
    Bip,
    Comando,
    CortarFala,
    Digitado,
    Efeito,
    EnviarAoCerebro,
    Estado,
    Evento,
    FalaAoVivo,
    FalaOcioso,
    Falar,
    FecharMicrofone,
    FecharPedido,
    FimDeFala,
    Frase,
    InterromperCerebro,
    Interrompido,
    PedidoAprovacao,
    Presenca,
    ResponderAprovacao,
    RespostaFim,
    ReterAviso,
    Silencio,
    Soltou,
    Tempo,
)

# Quem importa daqui continua importando daqui: os nomes moram nos três módulos acima.
__all__ = [
    "APROVA",
    "APROVA_NO_COMECO",
    "BRILHO_SEM_ALVO",
    "CHAMADOS",
    "COMANDOS",
    "CONCORDANCIAS",
    "CORRIGE",
    "ENCERRAR_APOIO",
    "ENCERRAR_PRINCIPAIS",
    "FALAS_DAS_AREAS",
    "INTERROMPER",
    "MANUTENCAO_APOIO",
    "MANUTENCAO_DESLIGAR",
    "MANUTENCAO_LIGAR",
    "NAO_ENTENDI",
    "NEGA",
    "NOMES",
    "OFERTA",
    "ORBES_PADRAO",
    "ORBE_ARTIGOS",
    "ORBE_DENTRO",
    "ORBE_TIPOS",
    "ORBE_VERBOS",
    "PRAZO_AO_VIVO_S",
    "PRAZO_CONFIRMACAO_S",
    "PRAZO_CONVERSA_S",
    "PRAZO_ESCUTA_S",
    "PRAZO_SEGURANDO_S",
    "REPERGUNTA",
    "RESPOSTA_CURTA",
    "TROCAR_APOIO",
    "TROCAR_NOMES",
    "TROCAR_VERBOS",
    "TUDO",
    "VACILOS",
    "WHATSAPP_LOCAL",
    "_DE",
    "_NAO_E_NOME",
    "_WA",
    "AbrirMicrofone",
    "AoVivo",
    "Apertou",
    "AprovacaoExpirou",
    "Ativacao",
    "Aviso",
    "Bip",
    "Comando",
    "CortarFala",
    "Digitado",
    "Efeito",
    "EnviarAoCerebro",
    "Estado",
    "Evento",
    "FalaAoVivo",
    "FalaOcioso",
    "Falar",
    "FecharMicrofone",
    "FecharPedido",
    "FimDeFala",
    "Frase",
    "InterromperCerebro",
    "Interrompido",
    "Maquina",
    "PedidoAprovacao",
    "Presenca",
    "ResponderAprovacao",
    "RespostaFim",
    "ReterAviso",
    "Silencio",
    "Soltou",
    "Tempo",
    "_parece_manutencao",
    "comando",
    "encerra",
    "entender_resposta",
    "manutencao",
    "orbe",
    "palavras",
    "pedido_valido",
    "resposta_a_oferta",
    "resposta_a_permissao",
    "sem_chamado",
    "sem_nome",
    "so_concordancia",
    "troca",
    "whatsapp_local",
]

PRAZO_ESCUTA_S = 20.0
PRAZO_SEGURANDO_S = 120.0  # botão apertado: o pedido fecha ao soltar, não no silêncio
PRAZO_AO_VIVO_S = 24 * 3600.0  # ao vivo: o silêncio não encerra a escuta
PRAZO_CONVERSA_S = 8.0
PRAZO_CONFIRMACAO_S = 40.0


@dataclass
class Maquina:
    estado: Estado = Estado.INATIVO
    autorizado: bool = False
    prazo: float = 0.0
    cerebro_terminou: bool = True
    pergunta_falando: bool = False
    em_conversa: bool = False  # aberta por "Ei Zé"; fechada por "ok", silêncio ou janela
    continuacao: bool = False  # pergunta seguinte da conversa (sem "Ei Zé")
    aviso_falando: str | None = None  # aviso em fala; cortado, volta para a fila
    escutar_depois: bool = False  # o aviso em fala abre a escuta ao terminar (mãos livres)
    reperguntou: bool = False  # a confirmação já foi repetida uma vez por resposta confusa
    segurando: bool = False  # botão de falar apertado: o pedido fecha ao soltar
    em_ligacao: bool = False  # uma ligação do WhatsApp no app (ADR 0066): os avisos esperam
    ao_vivo: bool = False  # "Conectar voz": ouve sem parar até desconectar (ADR 0023)
    prazo_conversa_s: float = PRAZO_CONVERSA_S
    historico: list[Estado] = field(default_factory=list)
    # O laço liga ao Hyprland: o Núcleo é a janela ativa agora? (desambigua "aumenta o brilho")
    nucleo_em_foco: Callable[[], bool] = field(default=lambda: False)
    # Os orbes pelo nome falado (manifesto do Núcleo; o laço preenche).
    orbes: dict[str, str] = field(default_factory=lambda: dict(ORBES_PADRAO))
    # Uma oferta de avisos acabou de ser feita ("Começo pela Loja?", ADR 0029): "sim", "próximo"
    # e "depois" respondem a ela, não vão ao cérebro.
    oferta: Callable[[], bool] = field(default=lambda: False)
    # A pergunta de permissão de uma sessão acabou de ser feita (ADR 0039): "sim" e "não" a
    # respondem, sem passar pelo cérebro.
    permissao: Callable[[], bool] = field(default=lambda: False)
    # A última fala do Zé foi uma pergunta ("Quer que eu ligue?"): ao vivo, o "beleza" responde.
    ze_perguntou: Callable[[], bool] = field(default=lambda: False)

    # --- o que o laço consulta ----------------------------------------------------------

    @property
    def microfone_aberto(self) -> bool:
        return self.estado is not Estado.INATIVO

    @property
    def detector_ligado(self) -> bool:
        return self.estado in (Estado.ATIVO, Estado.PENSANDO, Estado.FALANDO)

    @property
    def transcrevendo(self) -> bool:
        if self.estado is Estado.CONFIRMANDO:
            return not self.pergunta_falando
        return self.estado is Estado.OUVINDO

    @property
    def anel(self) -> str:
        """Estado no vocabulário do Barehands: idle | listening | thinking | speaking."""
        return {
            Estado.INATIVO: "idle",
            Estado.ATIVO: "idle",
            Estado.OUVINDO: "listening",
            Estado.PENSANDO: "thinking",
            Estado.FALANDO: "speaking",
            Estado.CONFIRMANDO: "speaking" if self.pergunta_falando else "listening",
        }[self.estado]

    # --- transições ---------------------------------------------------------------------

    def _ir(self, estado: Estado) -> None:
        if estado is not self.estado:
            self.historico.append(estado)
        self.estado = estado
        # O botão vale para um pedido: saiu da escuta (fechou, foi ao cérebro), deixa de estar
        # apertado, tenha o "soltar" chegado ou não. Sem isto, um soltar perdido (o painel
        # fechado com o "Falar" travado) fazia todo pedido seguinte esperar o teto de 60 s.
        if estado not in (Estado.OUVINDO, Estado.CONFIRMANDO):
            self.segurando = False

    def tratar(self, evento: Evento, agora: float) -> list[Efeito]:
        if isinstance(evento, Presenca):
            return self._presenca(evento.ativo, agora)
        if isinstance(evento, AoVivo):
            return self._mudar_ao_vivo(evento.ligado, agora)
        if self.estado is Estado.INATIVO:
            # Invariante 1: inativo não ouve, não fala e não segura pedido algum.
            return [ReterAviso(evento.texto)] if isinstance(evento, Aviso) else []
        match evento:
            case Ativacao():
                return self._ativacao(agora)
            case Apertou():
                return self._apertou(agora)
            case Soltou():
                if not self.segurando:
                    return []
                self.segurando = False
                return [FecharPedido()]
            case FimDeFala(texto) | FalaAoVivo(texto) if (
                self.estado is Estado.OUVINDO and sem_chamado(texto) is None
            ):
                # Só o chamado de novo (não ouviu o bip, ou repetiu): segue ouvindo, sem "não
                # entendi".
                self.prazo = agora + PRAZO_ESCUTA_S
                return [Bip()] if self.autorizado else []
            case FimDeFala(texto) | FalaAoVivo(texto):
                return self._fim_de_fala(texto)
            case Interrompido():
                return self._interrompido(agora)
            case Digitado(texto):
                return self._digitado(texto)
            case Silencio():
                return self._silencio()
            case Frase(texto):
                return self._frase(texto)
            case RespostaFim():
                self.cerebro_terminou = True
                return [] if self.estado is not Estado.PENSANDO else self._voltar(agora)
            case FalaOcioso():
                return self._fala_ociosa(agora)
            case PedidoAprovacao(descricao):
                return self._pedido_aprovacao(descricao)
            case AprovacaoExpirou():
                if self.estado is not Estado.CONFIRMANDO:
                    return []
                self.pergunta_falando = False
                self._ir(Estado.PENSANDO)  # o cérebro segue com a negativa: a resposta dele vem
                return [CortarFala()]
            case Aviso(texto, escutar, sequencial):
                if self.em_ligacao:
                    return [ReterAviso(texto)]  # você está falando com alguém pelo app
                if self.estado is Estado.ATIVO or (
                    (self.ao_vivo or sequencial)
                    and self.estado is Estado.OUVINDO
                    and not self.segurando
                ):
                    self._ir(Estado.FALANDO)
                    self.aviso_falando = texto
                    self.escutar_depois = escutar
                    return [Falar(texto)]
                return [ReterAviso(texto)]
            case Tempo():
                return self._tempo(agora)
        return []

    def _mudar_ao_vivo(self, ligado: bool, agora: float) -> list[Efeito]:
        self.ao_vivo = ligado
        if ligado and self.estado is Estado.ATIVO:
            return [*self._ouvir_ao_vivo(agora), Bip()]
        if not ligado and self.estado is Estado.OUVINDO and not self.segurando:
            self.autorizado = self.em_conversa = False
            self._ir(Estado.ATIVO)
        return []

    def _ouvir_ao_vivo(self, agora: float) -> list[Efeito]:
        """Ao vivo: o próximo pedido vem sem chamado, e o silêncio não encerra a escuta."""
        self._ir(Estado.OUVINDO)
        self.autorizado = self.em_conversa = True
        self.continuacao = False
        self.prazo = agora + PRAZO_AO_VIVO_S
        return []

    def _presenca(self, ativo: bool, agora: float = 0.0) -> list[Efeito]:
        if not ativo:
            if self.estado is Estado.INATIVO:
                return []
            efeitos: list[Efeito] = [CortarFala(), FecharMicrofone(), *self._aviso_cortado()]
            if self.estado is Estado.CONFIRMANDO:
                efeitos.append(ResponderAprovacao(aprovado=False))
            if not self.cerebro_terminou:
                efeitos.append(InterromperCerebro())
            self._reiniciar()
            return efeitos
        if self.estado is not Estado.INATIVO:
            return []
        self._ir(Estado.ATIVO)
        if self.ao_vivo:
            return [AbrirMicrofone(), *self._ouvir_ao_vivo(agora), Bip()]
        return [AbrirMicrofone()]

    def _reiniciar(self) -> None:
        self.segurando = False
        self._ir(Estado.INATIVO)
        self.autorizado = False
        self.cerebro_terminou = True
        self.pergunta_falando = False
        self.em_conversa = False

    def _ativacao(self, agora: float) -> list[Efeito]:
        if not self.detector_ligado:
            return []
        efeitos: list[Efeito] = []
        if self.estado in (Estado.PENSANDO, Estado.FALANDO):
            # "Ei Zé" no meio da resposta interrompe e já abre um pedido novo. Só interrompe o
            # cérebro se ele estiver respondendo: no meio de um aviso não há o que interromper, e
            # a interrupção à toa refazia a sessão (contexto perdido, teste de 06/10/2026).
            efeitos += [CortarFala(), *self._aviso_cortado()]
            if not self.cerebro_terminou:
                efeitos.append(InterromperCerebro())
            self.cerebro_terminou = True
        self._ir(Estado.OUVINDO)
        self.autorizado = True
        self.em_conversa = True
        self.continuacao = False
        self.prazo = agora + PRAZO_ESCUTA_S
        return [*efeitos, Bip()]

    def _apertou(self, agora: float) -> list[Efeito]:
        """O botão vale como o chamado, com ou sem o "Ei Zé" ligado; numa confirmação, é a
        resposta que vem."""
        if self.estado is Estado.CONFIRMANDO:
            self.segurando = not self.pergunta_falando
            return []
        efeitos = [] if self.estado is Estado.OUVINDO else self._ativacao(agora)
        if self.estado is Estado.OUVINDO:
            self.segurando = self.autorizado = True
            self.prazo = agora + PRAZO_SEGURANDO_S
            # O botão é um pedido só: depois da resposta, o Zé espera o botão de novo (ao vivo,
            # continua ouvindo como antes).
            self.em_conversa = self.ao_vivo
            self.continuacao = False
        return efeitos

    def _fim_de_fala(self, texto: str) -> list[Efeito]:
        if self.estado is Estado.CONFIRMANDO and not self.pergunta_falando:
            decisao = entender_resposta(texto)
            if decisao is None and not self.reperguntou:
                self.reperguntou = True
                self.pergunta_falando = True  # o eco da nova pergunta também não aprova
                return [Falar(REPERGUNTA)]
            return self._responder(bool(decisao), texto)
        if self.estado is not Estado.OUVINDO or not self.autorizado:
            return []
        self.autorizado = False  # invariante 2: um pedido por autorização
        texto = sem_chamado(texto) or texto
        if self.permissao() and (nome := resposta_a_permissao(texto)):
            # Antes do "ok" que encerra a conversa: "ok, pode" responde à sessão (ADR 0039).
            self._ir(Estado.PENSANDO)
            self.cerebro_terminou = False
            return [Comando(nome)]
        so_hesitacao = set(palavras(texto)) <= VACILOS
        concorda = so_concordancia(texto) and not self.ze_perguntou()
        if self.ao_vivo and (
            encerra(texto) or so_hesitacao or concorda or not pedido_valido(texto)
        ):
            # Ao vivo, "ok", "entendi", ruído e frase solta não encerram nem pedem repetição:
            # segue ouvindo.
            self.autorizado = True
            return []
        if encerra(texto):
            self.em_conversa = False
            self._ir(Estado.ATIVO)
            return [Bip()]
        if not pedido_valido(texto):
            if self.continuacao:
                # Ruído ou fala que o Whisper não entendeu depois de uma resposta: encerra em
                # silêncio. Responder "não entendi" e ouvir de novo virava um laço sem fim.
                self.em_conversa = False
                self._ir(Estado.ATIVO)
                return []
            if not palavras(texto):
                # Nada transcrito (ativação falsa, botão sem fala): fecha com o bip. "Não
                # entendi" soava como erro de algo que ninguém pediu.
                self.em_conversa = False
                self._ir(Estado.ATIVO)
                return [Bip()]
            return self._dizer(NAO_ENTENDI)
        self._ir(Estado.PENSANDO)
        self.cerebro_terminou = False
        # O comando responde como o cérebro responderia (Frase e RespostaFim), pelo núcleo.
        return [self._pedido(texto)]

    def _digitado(self, texto: str) -> list[Efeito]:
        """O Teclado: escrever é pedir. Responde a uma confirmação pendente, corta a resposta em
        andamento (como "Ei Zé") e não abre conversa por voz depois."""
        if self.estado is Estado.CONFIRMANDO:
            # Escrito, "sim" ou "não" vale na hora; o que não for nenhum dos dois é uma correção.
            self.pergunta_falando = False
            return [CortarFala(), *self._responder(bool(entender_resposta(texto)), texto)]
        if not pedido_valido(texto):
            return []
        efeitos: list[Efeito] = []
        if self.estado in (Estado.PENSANDO, Estado.FALANDO):
            efeitos += [CortarFala(), *self._aviso_cortado()]
            if not self.cerebro_terminou:
                efeitos.append(InterromperCerebro())
        self.autorizado = False
        self.em_conversa = False
        self.continuacao = False
        self._ir(Estado.PENSANDO)
        self.cerebro_terminou = False
        return [*efeitos, self._pedido(texto)]

    def _pedido(self, texto: str) -> Efeito:
        """Comando local ou o cérebro. O modo manutenção não captura a fala (ADR 0072): um
        pedido ao autodesenvolvimento é explícito e vai pelo cérebro."""
        if self.permissao() and (nome := resposta_a_permissao(texto)):  # o Teclado também
            return Comando(nome)
        if self.oferta() and (nome := resposta_a_oferta(texto)):
            return Comando(nome)
        if nome := comando(texto, self.nucleo_em_foco(), self.orbes):
            return Comando(nome)
        return EnviarAoCerebro(texto)

    def _silencio(self) -> list[Efeito]:
        if self.estado is Estado.OUVINDO and self.ao_vivo:
            self.autorizado = True
        elif self.estado is Estado.OUVINDO:
            self.autorizado = False
            self.em_conversa = False
            self._ir(Estado.ATIVO)
        elif self.estado is Estado.CONFIRMANDO and not self.pergunta_falando:
            return self._responder(False)
        return []

    def _frase(self, texto: str) -> list[Efeito]:
        if self.estado not in (Estado.PENSANDO, Estado.FALANDO):
            return []  # resposta de um pedido interrompido: descartada
        self._ir(Estado.FALANDO)
        return [Falar(texto)]

    def _fala_ociosa(self, agora: float) -> list[Efeito]:
        if self.estado is Estado.CONFIRMANDO and self.pergunta_falando:
            # Só depois da pergunta terminar o microfone transcreve (eco) e o prazo começa.
            self.pergunta_falando = False
            self.prazo = agora + PRAZO_CONFIRMACAO_S
            return [Bip()]
        if self.estado is Estado.FALANDO:
            return self._voltar(agora)
        return []

    def _aviso_cortado(self) -> list[Efeito]:
        """Aviso interrompido no meio não se perde: volta para a fila (teste de 06/10/2026)."""
        aviso, self.aviso_falando = self.aviso_falando, None
        return [ReterAviso(aviso)] if aviso else []

    def _voltar(self, agora: float) -> list[Efeito]:
        escutar = self.aviso_falando is not None and self.escutar_depois
        self.aviso_falando, self.escutar_depois = None, False
        if not self.cerebro_terminou:
            self._ir(Estado.PENSANDO)
        elif escutar:
            # Mãos livres: o aviso abre a conversa; "diz pra ela rodar os testes" sem "Ei Zé".
            self.em_conversa = True
            self._ir(Estado.OUVINDO)
            self.autorizado = True
            self.continuacao = True
            self.prazo = agora + self.prazo_conversa_s
            return [Bip()]
        elif self.ao_vivo:
            self._ouvir_ao_vivo(agora)
        elif self.em_conversa:
            # Conversa aberta pelo usuário: a resposta concede a próxima pergunta sem "Ei Zé".
            self._ir(Estado.OUVINDO)
            self.autorizado = True
            self.continuacao = True
            self.prazo = agora + self.prazo_conversa_s
        else:
            self._ir(Estado.ATIVO)
        return []

    def _interrompido(self, agora: float) -> list[Efeito]:
        """Live: a pessoa falou por cima. O que o Zé dizia para (o aviso volta para a fila), o
        cérebro que ainda respondia é interrompido e a vez é dela: o que ela disser é o próximo
        pedido. Numa confirmação, cortar a pergunta já é começar a responder."""
        if self.estado is Estado.CONFIRMANDO:
            if self.pergunta_falando:
                self.pergunta_falando = False
                self.prazo = agora + PRAZO_CONFIRMACAO_S
            return []
        if self.estado not in (Estado.PENSANDO, Estado.FALANDO):
            return []
        efeitos: list[Efeito] = [CortarFala(), *self._aviso_cortado()]
        if not self.cerebro_terminou:
            efeitos.append(InterromperCerebro())
        self.cerebro_terminou = True
        if self.ao_vivo:
            self._ouvir_ao_vivo(agora)
        else:
            self._ir(Estado.OUVINDO)
            self.autorizado = self.em_conversa = True
            self.prazo = agora + self.prazo_conversa_s
        return efeitos

    def _pedido_aprovacao(self, descricao: str) -> list[Efeito]:
        if self.estado not in (Estado.PENSANDO, Estado.FALANDO):
            return [ResponderAprovacao(aprovado=False)]
        self._ir(Estado.CONFIRMANDO)
        self.pergunta_falando = True
        self.reperguntou = False
        pergunta = descricao.rstrip()
        return [Falar(pergunta if pergunta.endswith("?") else f"{pergunta} Posso?")]

    def _responder(self, aprovado: bool, fala: str = "") -> list[Efeito]:
        self._ir(Estado.PENSANDO)
        return [ResponderAprovacao(aprovado, fala)]

    def _tempo(self, agora: float) -> list[Efeito]:
        if agora < self.prazo:
            return []
        if self.estado is Estado.CONFIRMANDO and not self.pergunta_falando:
            return self._responder(False)
        return []

    def _dizer(self, texto: str) -> list[Efeito]:
        self._ir(Estado.FALANDO)
        self.cerebro_terminou = True
        return [Falar(texto)]
