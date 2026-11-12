"""Os comandos locais da voz (`zervis/nucleo/estados.py`): o que o Zé resolve sem o cérebro,
pela frase inteira (a tabela `COMANDOS`), trocar de cérebro, o modo manutenção, abrir e fechar
orbes e as leituras do WhatsApp. Funções puras, sem estado."""

import difflib
import re

from zervis.nucleo.entender import (
    APROVA_NO_COMECO,
    CORRIGE,
    NEGA,
    RESPOSTA_CURTA,
    TUDO,
    palavras,
    sem_nome,
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
    # O pedido de permissão de uma sessão (ADR 0039), a qualquer momento: o Zé responde ao que
    # espera (o último que perguntou) e diz se não há nada esperando.
    "permissao_sim": {
        ("aprova",),
        ("aprovar",),
        ("aprovo",),
        ("aprove",),
        ("pode", "aprovar"),
        ("aprova", "a", "sessao"),
        ("aprova", "o", "pedido"),
        ("autoriza",),
        ("autoriza", "a", "sessao"),
    },
    # Todos os pedidos que esperam, da mesma sessão: uma pesquisa pedia um por site e o "aprova
    # tudo" ia para o cérebro, que dizia "aprovado" sem aprovar nada (caso real de 27/10/2026).
    "permissao_tudo": {
        (verbo, *resto)
        for verbo in ("aprova", "aprovar", "aprovo", "aprove", "autoriza", "autorizo")
        for resto in (("tudo",), ("todos",), ("todas",), ("tudo", "ai"), ("todos", "eles"))
    }
    | {("pode", "aprovar", "tudo"), ("pode", "aprovar", "todos"), ("pode", "autorizar", "tudo")},
    "permissao_nao": {
        ("nega",),
        ("negar",),
        ("nega", "a", "sessao"),
        ("nega", "o", "pedido"),
        ("nao", "aprova"),
        ("nao", "autoriza"),
        ("recusa",),
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
    "modo_avisos": {
        ("modo", "normal"),
        ("modo", "avisos"),  # o nome antigo continua valendo
        ("modo", "aviso"),
        ("modo", "de", "avisos"),
    },
    "modo_live": {
        ("modo", "live"),
        ("modo", "laive"),
        ("modo", "ao", "vivo"),
        ("modo", "maos", "livres"),  # o nome antigo continua valendo
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
    # Brilho da câmera e cores do Zé no Barehands (07/10/2026). "Da câmera" é
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
    # Avisos de lead quente no WhatsApp (14/10/2026).
    **{
        nome: {
            (verbo, *artigo, objeto, "do", *app)
            for verbo in verbos
            for artigo, objeto in ((("os",), "avisos"), ((), "avisos"), (("as",), "mensagens"))
            for app in (("whatsapp",), ("whats", "app"), ("zap",))
        }
        for nome, verbos in (
            ("whatsapp_liga", ("liga", "ligar", "ligue", "ativa", "ativar", "ative")),
            ("whatsapp_desliga", ("desliga", "desligar", "desligue", "desativa", "desativar")),
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
    # Sem "abre/fecha o Núcleo" desde 29/10/2026: não há mais orbes em volta do Zé (ADR 0047);
    # cada tela do Núcleo abre pelo nome ("abre o Guia"). A janela do Zé é outra coisa:
    # fechá-la apaga a câmera.
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
    # O visual do Zé na tela (07/10/2026): o avatar holográfico ou o anel original.
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
    "local": "local",  # o Ollama desta máquina (ADR 0063)
    "gemma": "local",
    "ollama": "local",
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


# As leituras do WhatsApp que o Zé responde sozinho, sem o cérebro e sem gastar token (ADR 0056):
# frases fechadas, inteiras; o resto ("o que a Ana disse do orçamento?") vai ao cérebro.
_WA = r"(?: (?:no|do|pelo) (?:whatsapp|whats app|zap))?"
_DE = r"(?:da|do|de|com a|com o|com)"
_NAO_E_NOME = {"e", "responde", "responder", "manda", "mandar", "diz", "fala", "resume", "depois"}
WHATSAPP_LOCAL = {
    "whatsapp_quem": (
        rf"quem (?:foi (?:a|o) ultim[ao](?: pessoa| contato)? (?:que|a) )?(?:me )?"
        rf"(?:mandou|enviou|escreveu)(?: (?:uma )?mensagem)?(?: (?:pra|para) mim)?{_WA}",
        rf"(?:de quem foi|qual foi|quem mandou) a ultima mensagem(?: que (?:eu )?recebi)?{_WA}",
        rf"(?:tem|chegou) (?:alguma )?mensagem(?: nova)?(?: (?:pra|para) mim)?{_WA}",
    ),
    "whatsapp_esperando": (
        rf"(?:tem )?(?:alguem|quem) (?:esta |ta )?esperando(?: (?:a )?(?:minha )?resposta)?{_WA}",
        rf"quem (?:eu )?(?:preciso|tenho que) responder{_WA}",
    ),
    "whatsapp_lista": (
        rf"quem (?:esta|ta) na (?:minha )?lista(?: de prioridade)?{_WA}",
        rf"quem (?:voce|vc) (?:esta|ta) monitorando{_WA}",
    ),
    "whatsapp_ler": (
        rf"(?:me )?(?:le|leia|ler)(?: (?:pra|para) mim)? (?:a |as )?(?:ultimas? )?"
        rf"(?:mensage(?:m|ns)|conversa) {_DE} (?P<nome>[a-z0-9]+(?: [a-z0-9]+){{0,2}}?){_WA}",
    ),
}


def whatsapp_local(texto: str) -> str | None:
    """`whatsapp_quem`, `whatsapp_esperando`, `whatsapp_lista` ou `whatsapp_ler:<nome>`."""
    frase = " ".join(texto) if isinstance(texto, tuple) else " ".join(palavras(texto))
    for nome, modelos in WHATSAPP_LOCAL.items():
        for modelo in modelos:
            if achado := re.fullmatch(modelo, frase):
                quem = achado.groupdict().get("nome")
                if quem and set(quem.split()) & _NAO_E_NOME:
                    return None  # "lê a da Ana e responde": pede mais que ler, vai ao cérebro
                return f"{nome}:{quem}" if quem else nome
    return None


def comando(
    texto: str, nucleo_em_foco: bool = False, orbes: dict[str, str] | None = None
) -> str | None:
    p = palavras(texto)
    if (limpo := sem_nome(p)) != p:
        p, texto = limpo, " ".join(limpo)
    if (nome := whatsapp_local(" ".join(p))) is not None:
        return nome
    if nucleo_em_foco and (nome := next((n for n, f in BRILHO_SEM_ALVO.items() if p in f), None)):
        return nome
    if (destino := troca(texto)) is not None:
        return f"trocar:{destino}"
    if (nome := manutencao(texto)) is not None:
        return nome
    return next((nome for nome, frases in COMANDOS.items() if p in frases), None) or orbe(
        texto, orbes
    )


ESCOLHA_LONGA = 25  # palavras: uma resposta de texto livre ao formulário cabe nisto


def resposta_a_escolha(texto: str) -> str | None:
    """Logo depois de uma pergunta de sessão com opções ("Qual delas?"), a fala inteira vai para
    a sessão escolher (`permissoes.escolher`), sem o cérebro. Pergunta, "repete" e fala longa
    demais seguem como pedido."""
    p = sem_nome(palavras(texto))
    if "?" in texto or p in COMANDOS["repetir"] or not 0 < len(p) <= ESCOLHA_LONGA:
        return None
    return "permissao_escolha:" + " ".join(texto.split())


def resposta_a_permissao(texto: str) -> str | None:
    """Logo depois da pergunta de uma sessão ("Aprovo?"), uma resposta curta: o não ganha de
    tudo (uma negação ou correção em qualquer lugar); o sim precisa vir no começo ("sim",
    "pode publicar"). A janela dura a pergunta e a escuta, então pergunta ("vai chover
    amanhã?"), frase longa e "não entendi" seguem como pedido e não decidem nada."""
    p = sem_nome(palavras(texto))
    if "?" in texto or p in COMANDOS["repetir"] or not 0 < len(p) <= RESPOSTA_CURTA:
        return None
    if set(p) & (NEGA | CORRIGE):
        return "permissao_nao"
    if p[0] not in APROVA_NO_COMECO:
        return None
    return "permissao_tudo" if set(p) & TUDO else "permissao_sim"
