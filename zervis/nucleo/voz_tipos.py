"""Os estados, os eventos que a máquina de voz recebe e os efeitos que ela devolve
(`zervis/nucleo/estados.py`): só dados, sem regra."""

from dataclasses import dataclass
from enum import Enum


class Estado(Enum):
    INATIVO = "inativo"
    ATIVO = "ativo"
    OUVINDO = "ouvindo"
    PENSANDO = "pensando"
    FALANDO = "falando"
    CONFIRMANDO = "confirmando"


# --- eventos -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Presenca:
    ativo: bool


@dataclass(frozen=True)
class Ativacao:
    """O detector ouviu "Ei Zé"."""


@dataclass(frozen=True)
class FimDeFala:
    """Transcrição do que o usuário disse depois da ativação (ou da pergunta de confirmação)."""

    texto: str


@dataclass(frozen=True)
class Digitado:
    """Pedido escrito no Teclado do Núcleo: vale como fala autorizada, sem "Ei Zé"."""

    texto: str


@dataclass(frozen=True)
class Silencio:
    """O prazo de escuta acabou sem fala."""


@dataclass(frozen=True)
class Frase:
    """Uma frase pronta do cérebro, para falar já."""

    texto: str


@dataclass(frozen=True)
class RespostaFim:
    """O cérebro terminou a resposta."""


@dataclass(frozen=True)
class FalaOcioso:
    """A saída de voz terminou tudo o que tinha para falar."""


@dataclass(frozen=True)
class PedidoAprovacao:
    descricao: str


@dataclass(frozen=True)
class AprovacaoExpirou:
    """O cérebro desistiu de esperar a confirmação (rede de segurança): sai da pergunta."""


@dataclass(frozen=True)
class Aviso:
    texto: str
    escutar: bool = False  # mãos livres: depois do aviso, ouve a resposta sem o chamado
    sequencial: bool = False  # resultados de sessões saem também nas pausas da conversa
    pedido: bool = False  # a pessoa pediu para ouvir (o "Ouvir" do celular): vale no Silencioso


@dataclass(frozen=True)
class Tempo:
    """Batida do relógio do laço, para os prazos."""


@dataclass(frozen=True)
class Apertou:
    """O botão de falar foi apertado (painel, atalho ou fone): vale como o chamado."""


@dataclass(frozen=True)
class Soltou:
    """O botão de falar foi solto: o pedido fecha agora."""


@dataclass(frozen=True)
class AoVivo:
    """A voz ao vivo ligou ou desligou ("Conectar voz"): ouvir sem parar, sem o chamado."""

    ligado: bool


@dataclass(frozen=True)
class FalaAoVivo:
    """Uma fala da pessoa pelo Live (ADR 0042): a vez dela fechou e o texto veio junto. Vale
    como o `FimDeFala`; os instantes alimentam as latências (fim da fala e fim da vez)."""

    texto: str
    fim_fala_em: float = 0.0
    fechado_em: float = 0.0


@dataclass(frozen=True)
class Interrompido:
    """No Live, a pessoa falou por cima do Zé e a fala foi cortada (ADR 0042)."""


Evento = (
    Presenca
    | Ativacao
    | FimDeFala
    | Digitado
    | Silencio
    | Frase
    | RespostaFim
    | FalaOcioso
    | PedidoAprovacao
    | AprovacaoExpirou
    | Aviso
    | Tempo
    | Apertou
    | Soltou
    | AoVivo
    | FalaAoVivo
    | Interrompido
)

# --- efeitos -------------------------------------------------------------------------------


@dataclass(frozen=True)
class AbrirMicrofone:
    pass


@dataclass(frozen=True)
class FecharMicrofone:
    pass


@dataclass(frozen=True)
class CortarFala:
    pass


@dataclass(frozen=True)
class Bip:
    pass


@dataclass(frozen=True)
class EnviarAoCerebro:
    texto: str


@dataclass(frozen=True)
class InterromperCerebro:
    pass


@dataclass(frozen=True)
class Falar:
    texto: str


@dataclass(frozen=True)
class ResponderAprovacao:
    aprovado: bool
    fala: str = ""  # o que o usuário disse; numa correção, o cérebro ajusta o pedido


@dataclass(frozen=True)
class ReterAviso:
    texto: str


@dataclass(frozen=True)
class FecharPedido:
    """O botão foi solto: o laço fecha o pedido com o que já ouviu, sem esperar a pausa."""


@dataclass(frozen=True)
class Comando:
    """Pedido resolvido no próprio Zé, sem o cérebro ("nova conversa", "relatório de uso")."""

    nome: str


Efeito = (
    AbrirMicrofone
    | FecharMicrofone
    | CortarFala
    | Bip
    | EnviarAoCerebro
    | InterromperCerebro
    | Falar
    | ResponderAprovacao
    | ReterAviso
    | Comando
    | FecharPedido
)
