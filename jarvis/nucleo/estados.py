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

import difflib
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
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
    """O detector ouviu "Hey Orca"."""


@dataclass(frozen=True)
class FimDeFala:
    """Transcrição do que o usuário disse depois da ativação (ou da pergunta de confirmação)."""

    texto: str


@dataclass(frozen=True)
class Digitado:
    """Pedido escrito no Teclado do Núcleo: vale como fala autorizada, sem "Hey Orca"."""

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
class Aviso:
    texto: str
    escutar: bool = False  # mãos livres: depois do aviso, ouve a resposta sem o chamado


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
    | Aviso
    | Tempo
    | Apertou
    | Soltou
    | AoVivo
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
    """Pedido resolvido no próprio JARVIS, sem o cérebro ("nova conversa", "relatório de uso")."""

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

PRAZO_ESCUTA_S = 20.0
PRAZO_SEGURANDO_S = 120.0  # botão apertado: o pedido fecha ao soltar, não no silêncio
PRAZO_AO_VIVO_S = 24 * 3600.0  # ao vivo: o silêncio não encerra a escuta
PRAZO_CONVERSA_S = 8.0
PRAZO_CONFIRMACAO_S = 40.0
# Resposta à pergunta de confirmação (pedido do usuário, 06/10/2026: entender o que ele fala,
# não só "sim" e "não", que às vezes nem saem direito). Negação ou correção ganham de tudo:
# "pode não", "sim, mas troca o projeto" não aprovam. O que não der para entender pergunta de novo.
NEGA = {
    "nao",
    "nada",
    "negativo",
    "nunca",
    "jamais",
    "nem",
    "cancela",
    "cancelar",
    "espera",
    "pera",
    "deixa",  # "para" fica de fora: é preposição ("pode mandar para o Codex")
    "pare",
    "aguarda",
    "segura",
}
CORRIGE = {"mas", "porem", "troca", "muda", "outro", "outra", "antes"}
APROVA = {
    "sim",
    "si",
    "pode",
    "claro",
    "manda",
    "beleza",
    "blz",
    "ok",
    "okay",
    "okey",
    "isso",
    "vai",
    "confirmo",
    "confirmado",
    "positivo",
    "bora",
    "certo",
    "fechado",
    "autorizo",
    "autorizado",
    "faz",
    "faca",
    "perfeito",
    "exato",
    "exatamente",
    "show",
    "tranquilo",
    "demorou",
    "firmeza",
    "aham",
    "uhum",
    "yes",
    "valeu",
    "dale",
}
REPERGUNTA = "Não entendi. É sim ou não?"


def entender_resposta(texto: str) -> bool | None:
    """True aprova, False nega, None não deu para entender."""
    p = set(palavras(texto))
    if p & (NEGA | CORRIGE):
        return False
    if p & APROVA:
        return True
    return None


NAO_ENTENDI = "Não consegui entender. Pode repetir?"
# Frase curta feita só destas palavras, com pelo menos uma das principais, encerra a conversa.
# O Whisper escreve "Ok", "OK", "Okay", "Okey" e às vezes repete ("Ok, ok."). Teste de 06/10/2026:
# a lista exata ("ok" sozinho) não pegou o "ok" do usuário e a conversa não fechava.
# O comando "interromper" é "Hey Orca" (corta a resposta) seguido de uma destas ordens de parar:
# sem elas, "Hey Orca, para" ia ao cérebro como um pedido novo.
ENCERRAR_PRINCIPAIS = {"ok", "okay", "okey", "obrigado", "valeu", "tchau", "chega", "parar"}
INTERROMPER = {"para", "pare", "interromper", "interrompe", "cancela", "cancelar", "silencio"}
ENCERRAR_PRINCIPAIS |= INTERROMPER
ENCERRAR_APOIO = {"ta", "bom", "pode", "entao", "por", "hoje", "muito", "e", "so", "isso", "ja"}
ENCERRAR_APOIO |= {"de", "falar", "a", "resposta", "jarvis", "ze"}


def encerra(texto: str) -> bool:
    p = palavras(texto)
    return (
        0 < len(p) <= 4
        and any(w in ENCERRAR_PRINCIPAIS for w in p)
        and all(w in ENCERRAR_PRINCIPAIS | ENCERRAR_APOIO for w in p)
    )


# As áreas do Mapa e como o usuário as chama: "mostra as sessões" é mostrar_sessoes.
FALAS_DAS_AREAS = {
    "memoria": (("a", "memoria"), ("sua", "memoria"), ("as", "memorias"), ("suas", "memorias")),
    "sessoes": (("as", "sessoes"), ("minhas", "sessoes"), ("os", "agentes"), ("meus", "agentes")),
    "automacoes": (
        ("as", "automacoes"),
        ("minhas", "automacoes"),
        ("os", "lembretes"),
        ("meus", "lembretes"),
        ("as", "tarefas"),
        ("minhas", "tarefas"),
    ),
}

COMANDOS = {
    # A central de avisos (ADR 0029): ouvir o que espera e o detalhe do último.
    "avisos_proximo": {
        ("proximo", "aviso"),
        ("quais", "avisos"),
        ("quais", "sao", "os", "avisos"),
        ("tem", "aviso"),
        ("tem", "algum", "aviso"),
        ("le", "os", "avisos"),
        ("ler", "os", "avisos"),
    },
    # Repetir a última fala (aviso ou resposta), na hora e igual, sem passar pelo cérebro.
    "repetir": {
        ("repete",),
        ("repita",),
        ("repete", "por", "favor"),
        ("repita", "por", "favor"),
        ("pode", "repetir"),
        ("repete", "ai"),
        ("fala", "de", "novo"),
        ("nao", "entendi"),
        ("nao", "ouvi"),
        ("o", "que", "voce", "disse"),
    },
    "aviso_detalhe": {
        ("o", "que", "ela", "disse"),
        ("o", "que", "ele", "disse"),
        ("o", "que", "a", "sessao", "disse"),
        ("le", "a", "resposta"),
        ("ler", "a", "resposta"),
        ("mais", "detalhes"),
        ("detalhes",),
    },
    # O modo de fala (ADR 0018). Silencioso fecha a escuta: volta pelo painel ou pelo atalho.
    "modo_silencioso": {
        ("modo", "silencioso"),
        ("fica", "em", "silencio"),
        ("fique", "em", "silencio"),
        ("silencio",),
    },
    "modo_avisos": {("modo", "avisos"), ("modo", "aviso"), ("modo", "de", "avisos")},
    "modo_maos_livres": {
        ("modo", "maos", "livres"),
        ("modo", "mao", "livre"),
        ("maos", "livres"),
    },
    "nova_conversa": {
        ("nova", "conversa"),
        ("conversa", "nova"),
        ("comecar", "uma", "nova", "conversa"),
        ("comeca", "uma", "nova", "conversa"),
    },
    "relatorio_de_uso": {
        ("relatorio", "de", "uso"),
        ("quanto", "eu", "ja", "usei"),
        ("quanto", "ja", "usei"),
        ("como", "esta", "o", "uso"),
        ("baterias",),
        ("como", "estao", "as", "baterias"),
        ("como", "esta", "a", "bateria"),
        ("quanto", "tem", "de", "bateria"),
    },
    # O mapa do cérebro no Barehands (06/10/2026): abre na tela sem gastar o cérebro.
    "mostrar_mapa": {
        (*inicio, *alvo)
        for inicio in (
            ("mostra",),
            ("mostrar",),
            ("me", "mostra"),
            ("abre",),
            ("abrir",),
        )
        for alvo in (
            ("o", "seu", "cerebro"),
            ("seu", "cerebro"),
            ("o", "cerebro"),
            ("o", "mapa"),
            ("o", "mapa", "do", "cerebro"),
            ("o", "mapa", "do", "seu", "cerebro"),
        )
    }
    | {("mapa", "do", "cerebro"), ("seu", "cerebro")},
    # Calibrador das mãos no Barehands (07/10/2026): guiado na tela, sem o cérebro.
    "calibrar_maos": {
        (verbo, *alvo)
        for verbo in ("calibra", "calibrar", "calibre")
        for alvo in (
            ("as", "maos"),
            ("a", "mao"),
            ("maos",),
            ("minhas", "maos"),
            ("minha", "mao"),
            ("as", "minhas", "maos"),
            ("a", "minha", "mao"),
        )
    }
    | {("calibracao", "das", "maos"), ("calibracao", "da", "mao")},
    "maos_padrao": {
        (*verbo, *alvo)
        for verbo in (("volta",), ("voltar",), ("volte",), ("restaura",), ("restaurar",))
        for alvo in (
            ("as", "maos", "ao", "padrao"),
            ("a", "calibracao", "padrao"),
            ("a", "calibracao", "original"),
            ("a", "calibracao", "das", "maos"),
            ("a", "camera", "ao", "padrao"),
        )
    }
    | {("calibracao", "padrao"), ("calibracao", "original")},
    # Brilho da câmera e cores do JARVIS no Barehands (07/10/2026). "Da câmera" é
    # obrigatório: o brilho da TELA é outra coisa e fica com o cérebro.
    **{
        nome: {
            (*verbo, *alvo)
            for verbo in verbos
            for alvo in (
                ("o", "brilho", "da", "camera"),
                ("brilho", "da", "camera"),
                ("o", "filtro", "da", "camera"),
                ("filtro", "da", "camera"),
            )
        }
        for nome, verbos in (
            ("brilho_mais", (("aumenta",), ("aumentar",), ("aumente",), ("sobe",), ("subir",))),
            ("brilho_menos", (("diminui",), ("diminuir",), ("diminua",), ("abaixa",), ("baixa",))),
            ("brilho_liga", (("liga",), ("ligar",), ("ativa",), ("ativar",), ("acende",))),
            ("brilho_desliga", (("desliga",), ("desligar",), ("desativa",), ("desativar",))),
        )
    },
    "configuracoes": {
        (*verbo, *alvo)
        for verbo in (("abre",), ("abrir",), ("mostra",), ("me", "mostra"))
        for alvo in (
            ("as", "configuracoes"),
            ("configuracoes",),
            ("o", "menu", "de", "configuracoes"),
        )
    },
    # O Núcleo (o anel do JARVIS com os orbes), 07/10/2026: abrir e recolher sem o cérebro. A
    # janela do JARVIS é outra coisa: fechá-la apaga a câmera.
    "nucleo_abrir": {
        (*verbo, *alvo)
        for verbo in (("abre",), ("abra",), ("abrir",), ("mostra",), ("mostre",), ("me", "mostra"))
        for alvo in (
            ("o", "nucleo"),
            ("nucleo",),
            ("seu", "nucleo"),
            ("o", "seu", "nucleo"),
            ("a", "sua", "interface"),
            ("sua", "interface"),
        )
    },
    "nucleo_fechar": {
        (*verbo, *alvo)
        for verbo in (("fecha",), ("feche",), ("fechar",), ("recolhe",), ("esconde",))
        for alvo in (
            ("o", "nucleo"),
            ("nucleo",),
            ("seu", "nucleo"),
            ("o", "seu", "nucleo"),
            ("a", "sua", "interface"),
        )
    },
    "janela_fechar": {
        (*verbo, *alvo)
        for verbo in (("fecha",), ("feche",), ("fechar",), ("desliga",))
        for alvo in (
            ("a", "janela", "do", "jarvis"),
            ("a", "sua", "janela"),
            ("sua", "janela"),
            ("a", "camera", "do", "jarvis"),
        )
    }
    | {("desliga", "o", "nucleo"), ("desliga", "a", "camera")},
    "reiniciar": {
        (*verbo, *alvo)
        for verbo in (("reinicia",), ("reinicie",), ("reiniciar",))
        for alvo in (("o", "jarvis"), ("jarvis",), ())
    }
    | {("se", "reinicia"), ("se", "reinicie")},
    "reiniciar:revisado": {
        (*verbo, *alvo, "eu", "revisei")
        for verbo in (("reinicia",), ("reinicie",))
        for alvo in (("o", "jarvis"), ())
    },
    "rodada_melhoria": {
        (*verbo, *alvo)
        for verbo in ((), ("faz", "uma"), ("faca", "uma"), ("comeca", "uma"), ("inicia", "uma"))
        for alvo in (("rodada", "de", "melhoria"), ("rodada", "de", "melhorias"))
    },
    # O visual do JARVIS na tela (07/10/2026): o avatar holográfico ou o anel original.
    "visual_avatar": {
        (*verbo, *alvo)
        for verbo in (
            ("mostra",),
            ("mostre",),
            ("usa",),
            ("use",),
            ("volta",),
            ("coloca",),
            ("liga",),
            ("ativa",),
            ("ative",),
        )
        for alvo in (("o", "avatar"), ("seu", "avatar"), ("avatar",), ("o", "seu", "avatar"))
    }
    | {("avatar",), ("modo", "avatar")},
    # O Zé dá uma volta completa na tela (08/10/2026, para humanizar o avatar).
    # O Foco (08/10/2026): onde ele parou e o que está pendente, sem gastar o cérebro.
    "foco_onde": {
        ("no", "que", "eu", "estava"),
        ("em", "que", "eu", "estava"),
        ("no", "que", "eu", "parei"),
        ("onde", "eu", "parei"),
        ("onde", "parei"),
        ("onde", "eu", "estava"),
        ("o", "que", "eu", "estava", "fazendo"),
        ("qual", "e", "o", "meu", "foco"),
        ("qual", "o", "meu", "foco"),
        ("qual", "e", "o", "foco"),
        ("qual", "e", "o", "meu", "foco", "agora"),
    },
    "foco_mostrar": {
        (*verbo, *alvo)
        for verbo in (
            ("mostra",),
            ("mostre",),
            ("abre",),
            ("abra",),
            ("aba",),
            ("ver",),
            ("quero", "ver"),
        )
        for alvo in (
            ("o", "meu", "foco"),
            ("meu", "foco"),
            ("o", "foco"),
            ("as", "minhas", "frentes"),
            ("minhas", "frentes"),
            ("o", "modo", "foco"),
            ("modo", "foco"),
            ("o", "quadro", "do", "foco"),
            ("a", "tela", "do", "foco"),
            ("o", "foco", "na", "tela"),
            ("o", "foco", "para", "eu", "ver"),
            ("o", "modo", "foco", "para", "eu", "ver"),
        )
    }
    | {("foco",), ("meu", "foco"), ("modo", "foco"), ("o", "modo", "foco")},
    "foco_pendentes": {
        ("o", "que", "esta", "pendente"),
        ("o", "que", "ta", "pendente"),
        ("o", "que", "tem", "pendente"),
        ("o", "que", "eu", "tenho", "pendente"),
        ("o", "que", "tenho", "pendente"),
        ("o", "que", "falta"),
        ("o", "que", "ficou", "pendente"),
        ("minhas", "frentes"),
        ("quais", "sao", "as", "minhas", "frentes"),
        ("quais", "sao", "minhas", "frentes"),
        ("mostra", "minhas", "frentes"),
    },
    "avatar_voltinha": {
        (*verbo, *giro, *fim)
        for verbo in (("da",), ("de",), ("faz",), ("faca",), ("da", "ai"), ("mostra",))
        for giro in (
            ("uma", "voltinha"),
            ("uma", "volta"),
            ("uma", "girada"),
            ("uma", "giradinha"),
            ("uma", "rodadinha"),
            ("um", "giro"),
            ("um", "girinho"),
        )
        for fim in ((), ("pra", "mim"), ("para", "mim"), ("ai",), ("ai", "pra", "mim"))
    }
    | {("gira",), ("gire",), ("gira", "ai"), ("roda",), ("roda", "ai"), ("vira", "uma", "volta")},
    "visual_anel": {
        (*verbo, *alvo)
        for verbo in (
            ("mostra",),
            ("mostre",),
            ("usa",),
            ("use",),
            ("volta",),
            ("coloca",),
            ("volta", "para"),
            ("volta", "pro"),
        )
        for alvo in (("o", "anel"), ("seu", "anel"), ("anel",))
    }
    | {("tira", "o", "avatar"), ("esconde", "o", "avatar"), ("desliga", "o", "avatar")},
    "teclado_abrir": {
        (*verbo, *alvo)
        for verbo in (("abre",), ("abra",), ("abrir",), ("mostra",), ("mostre",))
        for alvo in (("o", "teclado"), ("teclado",), ("seu", "teclado"))
    },
    "teclado_fechar": {
        (*verbo, *alvo)
        for verbo in (("fecha",), ("feche",), ("fechar",), ("esconde",))
        for alvo in (("o", "teclado"), ("teclado",), ("seu", "teclado"))
    },
    "mapa_fechar": {
        (*verbo, *alvo)
        for verbo in (("fecha",), ("fechar",), ("esconde",))
        for alvo in (("o", "seu", "cerebro"), ("seu", "cerebro"), ("o", "cerebro"), ("o", "mapa"))
    },
    **{
        f"mostrar_{area}": {
            (*verbo, *alvo)
            for verbo in (("mostra",), ("me", "mostra"), ("abre",), ("abra",), ("mostrar",))
            for alvo in alvos
        }
        for area, alvos in FALAS_DAS_AREAS.items()
    },
    # Temas de cor: "tema <cor>", "muda o tema para <cor>", "coloca/usa o tema <cor>".
    **{
        f"tema_{tema}": {
            frase
            for cor in cores
            for frase in (
                ("tema", *cor),
                ("o", "tema", *cor),
                ("muda", "o", "tema", "para", *cor),
                ("muda", "o", "tema", "pra", *cor),
                ("muda", "para", "o", "tema", *cor),
                ("coloca", "o", "tema", *cor),
                ("usa", "o", "tema", *cor),
                ("deixa", "o", "jarvis", *cor),
            )
        }
        for tema, cores in (
            ("roxo", (("roxo",), ("violeta",))),
            ("marinho", (("marinho",), ("azul", "marinho"))),
            ("esmeralda", (("esmeralda",), ("verde",))),
            ("grafite", (("grafite",), ("cinza",))),
        )
    },
    "tema_original": {
        ("tema", "original"),
        ("o", "tema", "original"),
        ("tema", "azul"),
        ("volta", "o", "tema", "original"),
        ("volta", "para", "o", "tema", "original"),
        ("volta", "pro", "tema", "original"),
        ("muda", "o", "tema", "para", "o", "original"),
        ("coloca", "o", "tema", "original"),
        ("deixa", "o", "jarvis", "azul"),
    },
}
# Troca de cérebro (ADR 0010): verbo + nome, com só palavras de apoio no meio. O Whisper
# escreve o GPT como "GPT", "G P T" ou "gpt"; as letras soltas são juntadas antes de comparar.
TROCAR_VERBOS = {"muda", "mudar", "troca", "trocar", "usa", "usar", "passa", "volta", "coloca"}
TROCAR_APOIO = {"para", "pra", "pro", "o", "a", "de", "cerebro", "modelo", "agora", "com", "no"}
TROCAR_NOMES = {
    "claude": "claude",
    "cloud": "claude",
    "clode": "claude",
    "sonnet": "claude",
    "gpt": "gpt",
    "chatgpt": "gpt",
    "codex": "gpt",
    "luna": "gpt",
    "gemini": "gemini",
    "jemini": "gemini",
    "geminai": "gemini",
    "automatico": "auto",
    "auto": "auto",
    "omniroute": "auto",
}


def troca(texto: str) -> str | None:
    p = palavras(texto)
    if not 2 <= len(p) <= 7 or p[0] not in TROCAR_VERBOS:
        return None
    nome = "".join(w for w in p[1:] if w not in TROCAR_APOIO)
    return TROCAR_NOMES.get(nome)


# "Aumenta o brilho" sem dizer de quê: é o da câmera do Núcleo quando ele é a janela ativa;
# fora dele, segue para o cérebro (o brilho do monitor, pelas ações do Omarchy).
BRILHO_SEM_ALVO = {
    nome: {
        (*verbo, *alvo)
        for verbo in verbos
        for alvo in (
            ("o", "brilho"),
            ("brilho",),
            ("o", "brilho", "ai"),
            ("um", "pouco", "o", "brilho"),
        )
    }
    for nome, verbos in (
        ("brilho_mais", (("aumenta",), ("aumentar",), ("aumente",), ("sobe",), ("mais",))),
        ("brilho_menos", (("diminui",), ("diminuir",), ("diminua",), ("abaixa",), ("menos",))),
        ("brilho_liga", (("liga",), ("ligar",), ("ativa",))),
        ("brilho_desliga", (("desliga",), ("desligar",), ("desativa",))),
    )
}


# O modo manutenção pela intenção, não por uma frase exata: "coloque no modo manutenção" foi ao
# cérebro em 07/10/2026 e virou o menu de configurações. Uma palavra parecida com "manutenção"
# (o Whisper erra: "manuntenção") mais um verbo de ligar, de desligar ou de perguntar a situação.
MANUTENCAO_LIGAR = {
    "entra",
    "entre",
    "entrar",
    "ativa",
    "ative",
    "ativar",
    "liga",
    "ligue",
    "ligar",
    "coloca",
    "coloque",
    "colocar",
    "bota",
    "bote",
    "botar",
    "poe",
    "ponha",
    "inicia",
    "inicie",
    "iniciar",
    "abre",
    "abra",
    "vai",
    "va",
    "vamos",
    "habilita",
    "habilite",
    "comeca",
    "comece",
}
MANUTENCAO_DESLIGAR = {
    "sai",
    "saia",
    "sair",
    "desliga",
    "desligue",
    "desligar",
    "desativa",
    "desative",
    "fecha",
    "feche",
    "encerra",
    "encerre",
    "termina",
    "termine",
    "finaliza",
    "finalize",
}
# Só vale como comando se a frase não tiver mais nada: "coloque um botão de manutenção no menu",
# no modo ligado, é um pedido para a sessão, não "ligar o modo".
MANUTENCAO_APOIO = (
    {
        "modo",
        "de",
        "o",
        "a",
        "em",
        "no",
        "na",
        "do",
        "da",
        "para",
        "pra",
        "pro",
        "por",
        "favor",
        "agora",
        "com",
        "codex",
        "claude",
        "cloud",
        "voce",
        "teu",  # "saia do teu modo manutenção" (08/10/2026) foi à sessão em vez de desligar
        "seu",
        "tua",
        "sua",
        "se",
        "entao",
        "ai",
        "me",
        "situacao",
        "status",
        "como",
        "esta",
        "ta",
        "anda",
        "vai",
    }
    | MANUTENCAO_LIGAR
    | MANUTENCAO_DESLIGAR
)


def _parece_manutencao(palavra: str) -> bool:
    return palavra.startswith("manu") and (
        difflib.SequenceMatcher(None, palavra, "manutencao").ratio() >= 0.75
    )


def manutencao(texto: str) -> str | None:
    p = sem_nome(palavras(texto))
    if not 1 <= len(p) <= 10 or not any(_parece_manutencao(w) for w in p):
        return None
    if "nao" in p or any(w not in MANUTENCAO_APOIO and not _parece_manutencao(w) for w in p):
        return None  # "o que é o modo manutenção?", "não entra...", um pedido: não é comando
    if any(w in MANUTENCAO_DESLIGAR for w in p):
        return "manutencao_sair"
    if any(w in ("situacao", "status") for w in p) or (
        p[0] == "como" and any(w in ("esta", "ta", "anda", "vai") for w in p)
    ):
        return "manutencao_situacao"
    agente = ":codex" if "codex" in p else ":claude" if {"claude", "cloud"} & set(p) else ""
    return "manutencao_entrar" + agente


# Os orbes pelo nome falado, do manifesto do Núcleo (o laço troca o padrão pelos de lá).
ORBES_PADRAO = {"mapa": "Mapa", "cerebro": "Mapa", "guia": "Guia", "acervo": "Acervo"}
ORBE_VERBOS = {
    **dict.fromkeys(("abre", "abra", "abrir", "mostra", "mostre"), "abrir"),
    **dict.fromkeys(("fecha", "feche", "fechar"), "fechar"),
}
ORBE_ARTIGOS = {"o", "a", "os", "as", "seu", "sua", "meu", "minha", "aba", "orbe", "painel"}
ORBE_DENTRO = {"do", "da", "no", "na"}
ORBE_TIPOS = {"arquivo", "nota", "modelo", "imagem", "pasta", "projeto", "agente", "tarefa"}


def orbe(texto: str, orbes: dict[str, str] | None = None) -> str | None:
    """Um orbe ou um item do Núcleo pelo nome: "abre o Guia" -> abrir_orbe:Guia; "abre o burrinho
    no Acervo" -> abrir_item:Acervo:burrinho; "abre o burrinho do núcleo" -> abrir_item::burrinho;
    "fecha o Guia" -> fechar_alvo:Guia. "Abre o burrinho", sem dizer onde, fica com o cérebro."""
    orbes = ORBES_PADRAO if orbes is None else orbes
    p = list(palavras(texto))
    if p[:2] == ["me", "mostra"]:
        p = p[1:]
    if not 2 <= len(p) <= 9 or (acao := ORBE_VERBOS.get(p[0])) is None:
        return None
    resto, dentro, do_nucleo = p[1:], None, False
    for n in (3, 2, 1):  # "... no Acervo", "... do seu núcleo"
        cauda = " ".join(resto[-n:])
        if len(resto) > n + 1 and resto[-n - 1] in ORBE_DENTRO:
            if cauda in ("nucleo", "seu nucleo"):
                resto, do_nucleo = resto[: -n - 1], True
                break
            if cauda in orbes:
                resto, dentro = resto[: -n - 1], orbes[cauda]
                break
    while resto and resto[0] in ORBE_ARTIGOS:
        resto = resto[1:]
    if len(resto) > 1 and resto[0] in ORBE_TIPOS:  # "o arquivo burrinho" -> burrinho
        resto = resto[1:]
    nome = " ".join(resto)
    if not nome and dentro is not None:  # "abre a aba do Guia": o próprio orbe
        nome = next(k for k, v in orbes.items() if v == dentro)
        dentro = None
    if not nome:
        return None
    if nome in orbes and dentro is None:
        return f"{acao}_orbe:{orbes[nome]}" if acao == "abrir" else f"fechar_alvo:{orbes[nome]}"
    if dentro is None and not do_nucleo:
        return None
    return f"abrir_item:{dentro or ''}:{nome}" if acao == "abrir" else f"fechar_alvo:{nome}"


# O nome falado (08/10/2026: o JARVIS passou a se chamar Zé; "Jarvis" ainda vale). Os comandos
# escritos com "o jarvis" ("reinicia o jarvis") valem com qualquer um dos nomes.
NOMES = {"jarvis", "ze"}
CHAMADOS = {
    ("ei", "ze"),
    ("hey", "ze"),
    ("hei", "ze"),
    ("ei", "jarvis"),
    ("hey", "jarvis"),
    # Como o Deepgram ouve "Ei Zé" às vezes (08/10/2026: "Eis é saia do modo manutenção").
    ("eis", "e"),
    ("ei", "se"),
    ("hey", "se"),
}
# Hesitações no começo da fala ("Um, desative o modo manutenção", 08/10/2026).
VACILOS = {"um", "uh", "hum", "hm", "ah", "ahn", "eh", "e"}


def so_chamado(texto: str) -> bool:
    """A fala é só o chamado ("Hey Zé"): no modo manutenção não vira pedido para a sessão."""
    p = palavras(texto)
    while p[:1] and p[0] in VACILOS:
        p = p[1:]
    return not p or p in CHAMADOS or (len(p) == 1 and p[0] in NOMES | {"ei", "hey", "oi"})


def sem_nome(p: tuple[str, ...]) -> tuple[str, ...]:
    """Tira o chamado ou o nome do começo ("Ei Zé, abre o guia") e põe "jarvis" no lugar de "zé"."""
    while len(p) > 1 and p[0] in VACILOS and p[:2] not in CHAMADOS:
        p = p[1:]
    if p[:2] in CHAMADOS and len(p) > 2:
        p = p[2:]
    elif p[:1] and p[0] in NOMES and len(p) > 1:  # "Zé, entra no modo manutenção"
        p = p[1:]
    return tuple("jarvis" if w == "ze" else w for w in p)


def comando(
    texto: str, nucleo_em_foco: bool = False, orbes: dict[str, str] | None = None
) -> str | None:
    p = palavras(texto)
    if (limpo := sem_nome(p)) != p:
        p, texto = limpo, " ".join(limpo)
    if nucleo_em_foco and (nome := next((n for n, f in BRILHO_SEM_ALVO.items() if p in f), None)):
        return nome
    if (destino := troca(texto)) is not None:
        return f"trocar:{destino}"
    if (nome := manutencao(texto)) is not None:
        return nome
    return next((nome for nome, frases in COMANDOS.items() if p in frases), None) or orbe(
        texto, orbes
    )


# Respostas a uma oferta de avisos (ADR 0029), só logo depois dela.
OFERTA = {
    "avisos_proximo": {
        ("sim",),
        ("pode",),
        ("comeca",),
        ("pode", "comecar"),
        ("vai",),
        ("manda",),
        ("proximo",),
        ("o", "proximo"),
        ("sim", "pode"),
    },
    "avisos_depois": {("depois",), ("agora", "nao"), ("nao",), ("mais", "tarde"), ("deixa",)},
}


def resposta_a_oferta(texto: str) -> str | None:
    p = sem_nome(palavras(texto))
    return next((nome for nome, frases in OFERTA.items() if p in frases), None)


def palavras(texto: str) -> tuple[str, ...]:
    """Minúsculas, sem acentos e sem pontuação: "Sim, pode!" -> ("sim", "pode")."""
    sem_acento = unicodedata.normalize("NFKD", texto.casefold())
    return tuple(
        re.findall(r"[^\W_]+", "".join(c for c in sem_acento if not unicodedata.combining(c)))
    )


def sem_chamado(texto: str) -> str | None:
    """O pedido sem o chamado do começo ("Ei Zé, que horas são?" -> "que horas são?"); o texto
    como veio se não começar pelo chamado; None se for só o chamado (a pessoa o repetiu ou não
    ouviu o bip; testes da voz pelo navegador, 12/10/2026)."""
    p = palavras(texto)
    so = p
    while so[:1] and so[0] in VACILOS and so[:2] not in CHAMADOS:
        so = so[1:]
    if so and (so in CHAMADOS or (len(so) == 1 and so[0] in NOMES)):
        return None
    n = 0
    while n < len(p) - 1 and p[n] in VACILOS and p[n : n + 2] not in CHAMADOS:
        n += 1
    if p[n : n + 2] in CHAMADOS:
        n += 2
    elif p[n : n + 1] and p[n] in NOMES:
        n += 1
    else:
        return texto
    return re.sub(rf"^\W*(?:\w+\W+){{{n - 1}}}\w+\W*", "", texto.strip())


def pedido_valido(texto: str) -> bool:
    return any(len(p) > 1 or p.isdigit() for p in palavras(texto))


@dataclass
class Maquina:
    estado: Estado = Estado.INATIVO
    autorizado: bool = False
    prazo: float = 0.0
    cerebro_terminou: bool = True
    pergunta_falando: bool = False
    em_conversa: bool = False  # aberta por "Hey Orca"; fechada por "ok", silêncio ou janela
    continuacao: bool = False  # pergunta seguinte da conversa (sem "Hey Orca")
    aviso_falando: str | None = None  # aviso em fala; cortado, volta para a fila
    escutar_depois: bool = False  # o aviso em fala abre a escuta ao terminar (mãos livres)
    reperguntou: bool = False  # a confirmação já foi repetida uma vez por resposta confusa
    segurando: bool = False  # botão de falar apertado: o pedido fecha ao soltar
    ao_vivo: bool = False  # "Conectar voz": ouve sem parar até desconectar (ADR 0023)
    prazo_conversa_s: float = PRAZO_CONVERSA_S
    historico: list[Estado] = field(default_factory=list)
    # O laço liga ao Hyprland: o Núcleo é a janela ativa agora? (desambigua "aumenta o brilho")
    nucleo_em_foco: Callable[[], bool] = field(default=lambda: False)
    # Os orbes pelo nome falado (manifesto do Núcleo; o laço preenche).
    orbes: dict[str, str] = field(default_factory=lambda: dict(ORBES_PADRAO))
    # Modo manutenção ligado: o que não for comando local vai para a sessão de código.
    manutencao: Callable[[], bool] = field(default=lambda: False)
    # Uma oferta de avisos acabou de ser feita ("Começo pela Loja?", ADR 0029): "sim", "próximo"
    # e "depois" respondem a ela, não vão ao cérebro.
    oferta: Callable[[], bool] = field(default=lambda: False)

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
            case FimDeFala(texto) if self.estado is Estado.OUVINDO and sem_chamado(texto) is None:
                # Só o chamado de novo (não ouviu o bip, ou repetiu): segue ouvindo, sem "não
                # entendi".
                self.prazo = agora + PRAZO_ESCUTA_S
                return [Bip()] if self.autorizado else []
            case FimDeFala(texto):
                return self._fim_de_fala(texto)
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
            case Aviso(texto, escutar):
                if self.estado is Estado.ATIVO or (
                    self.ao_vivo and self.estado is Estado.OUVINDO and not self.segurando
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
            # "Hey Orca" no meio da resposta interrompe e já abre um pedido novo. Só interrompe o
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
        so_hesitacao = set(palavras(texto)) <= VACILOS
        if self.ao_vivo and (encerra(texto) or so_hesitacao or not pedido_valido(texto)):
            # Ao vivo, "ok", ruído e frase solta não encerram nem pedem repetição: segue ouvindo.
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
        andamento (como "Hey Orca") e não abre conversa por voz depois."""
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
        """Comando local, a sessão de código (modo manutenção) ou o cérebro, nessa ordem."""
        if self.oferta() and (nome := resposta_a_oferta(texto)):
            return Comando(nome)
        if nome := comando(texto, self.nucleo_em_foco(), self.orbes):
            return Comando(nome)
        if self.manutencao() and not so_chamado(texto):
            return Comando(f"manutencao_pedido:{texto}")
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
            # Conversa aberta pelo usuário: a resposta concede a próxima pergunta sem "Hey Orca".
            self._ir(Estado.OUVINDO)
            self.autorizado = True
            self.continuacao = True
            self.prazo = agora + self.prazo_conversa_s
        else:
            self._ir(Estado.ATIVO)
        return []

    def _pedido_aprovacao(self, descricao: str) -> list[Efeito]:
        if self.estado not in (Estado.PENSANDO, Estado.FALANDO):
            return [ResponderAprovacao(aprovado=False)]
        self._ir(Estado.CONFIRMANDO)
        self.pergunta_falando = True
        self.reperguntou = False
        return [Falar(f"{descricao} Posso?")]

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
