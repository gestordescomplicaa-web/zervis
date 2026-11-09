"""Entender a fala curta da máquina de voz (`zervis/nucleo/estados.py`): sim e não numa
confirmação, o chamado ("Ei Zé"), encerrar a conversa, responder a uma oferta e as palavras
normalizadas. Funções puras, sem estado."""

import re
import unicodedata

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
TUDO = {"tudo", "todos", "todas"}  # "sim, aprova tudo": todos os pedidos da sessão
RESPOSTA_CURTA = 5  # palavras: "sim", "pode publicar", "não, deixa pra depois"
# O "sim" de uma permissão vem no começo e é claro: "vai", "faz" e "valeu" começam outras
# frases ("vai chover?", "faz um resumo", "valeu, Zé").
APROVA_NO_COMECO = (APROVA | {"aprova", "aprovado", "aprovo"}) - {
    "vai",
    "faz",
    "faca",
    "valeu",
    "demorou",
    "tranquilo",
    "firmeza",
}


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
# O comando "interromper" é "Ei Zé" (corta a resposta) seguido de uma destas ordens de parar:
# sem elas, "Ei Zé, para" ia ao cérebro como um pedido novo.
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


# O nome falado (08/10/2026: o Zé passou a se chamar Zé; "Jarvis" ainda vale). Os comandos
# escritos com "o jarvis" ("reinicia o jarvis") valem com qualquer um dos nomes.
NOMES = {"jarvis", "ze", "zervis"}  # "Zérvis, ..." também chama (03/11/2026)
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
# Ao vivo, quem conversa concorda enquanto ouve ("entendi", "beleza", "tá"). Sozinha, a
# concordância não é pedido: mandada ao cérebro, virava ação ("Entendi." ligou o modo manutenção
# no teste de 27/10/2026). Depois de uma pergunta do Zé, ela é a resposta e segue.
CONCORDANCIAS = {
    *("entendi", "entendido", "beleza", "blz", "certo", "ta", "bom", "show", "perfeito"),
    *("otimo", "legal", "uhum", "aham", "ahan", "sei", "isso", "massa", "joia", "ok", "okay"),
}


def so_concordancia(texto: str) -> bool:
    p = palavras(texto)
    return (
        0 < len(p) <= 3
        and all(w in CONCORDANCIAS | VACILOS for w in p)
        and any(w in CONCORDANCIAS for w in p)
    )


def sem_nome(p: tuple[str, ...]) -> tuple[str, ...]:
    """Tira o chamado ou o nome do começo ("Ei Zé, abre o guia") e põe "jarvis" no lugar de "zé"."""
    while len(p) > 1 and p[0] in VACILOS and p[:2] not in CHAMADOS:
        p = p[1:]
    if p[:2] in CHAMADOS and len(p) > 2:
        p = p[2:]
    elif p[:1] and p[0] in NOMES and len(p) > 1:  # "Zé, entra no modo manutenção"
        p = p[1:]
    return tuple("jarvis" if w == "ze" else w for w in p)


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
