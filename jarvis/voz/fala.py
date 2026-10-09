"""Texto de tela -> texto para a fala em português do Brasil.

Portado sem mudança de comportamento do JARVIS antigo (VIBE-CODING/jarvis/fala.py, 06/10/2026),
com `para_fala` vindo de `brain.speakable`. As sessões escrevem para leitura ("71%", "10:05",
"3,5 GB", "R$ 20"); o Cadu lê mal dígitos e símbolos, então tudo o que o JARVIS fala passa aqui.
"""

import re

UNIDADES = [
    "zero",
    "um",
    "dois",
    "três",
    "quatro",
    "cinco",
    "seis",
    "sete",
    "oito",
    "nove",
    "dez",
    "onze",
    "doze",
    "treze",
    "quatorze",
    "quinze",
    "dezesseis",
    "dezessete",
    "dezoito",
    "dezenove",
]
DEZENAS = [
    "",
    "",
    "vinte",
    "trinta",
    "quarenta",
    "cinquenta",
    "sessenta",
    "setenta",
    "oitenta",
    "noventa",
]
CENTENAS = [
    "",
    "cento",
    "duzentos",
    "trezentos",
    "quatrocentos",
    "quinhentos",
    "seiscentos",
    "setecentos",
    "oitocentos",
    "novecentos",
]
FEM = {
    "um": "uma",
    "dois": "duas",
    "duzentos": "duzentas",
    "trezentos": "trezentas",
    "quatrocentos": "quatrocentas",
    "quinhentos": "quinhentas",
    "seiscentos": "seiscentas",
    "setecentos": "setecentas",
    "oitocentos": "oitocentas",
    "novecentos": "novecentas",
}
# Substantivos femininos comuns nas respostas: o número antes deles concorda ("uma", "duas").
FEMININAS = "|".join(
    [
        "horas?",
        "semanas?",
        "vez",
        "vezes",
        "pessoas?",
        "tarefas?",
        "sess[aã]o",
        "sess[oõ]es",
        "mensage(?:m|ns)",
        "linhas?",
        "p[aá]ginas?",
        "abas?",
        "contas?",
        "chamadas?",
        "liga[cç][aã]o",
        "liga[cç][oõ]es",
        "vers[aã]o",
        "vers[oõ]es",
        "perguntas?",
        "respostas?",
        "sugest[aã]o",
        "sugest[oõ]es",
        "skills?",
        "entradas?",
        "janelas?",
        "portas?",
        "m[aá]quinas?",
        "coisas?",
        "op[cç][aã]o",
        "op[cç][oõ]es",
        "telas?",
        "image(?:m|ns)",
        "notas?",
        "noites?",
        "manh[aã]s?",
        "tardes?",
        "reuni[aã]o",
        "reuni[oõ]es",
        "frentes?",
        "pastas?",
        "falhas?",
        "mudan[cç]as?",
        "regras?",
        "contas?",
    ]
)
MESES = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]
ORD = {
    1: "primeiro",
    2: "segundo",
    3: "terceiro",
    4: "quarto",
    5: "quinto",
    6: "sexto",
    7: "sétimo",
    8: "oitavo",
    9: "nono",
    10: "décimo",
}

LETRAS = dict(
    zip(  # noqa: B905 (26 letras e 26 nomes, conferido nos testes)
        "abcdefghijklmnopqrstuvwxyz",
        [
            "á",
            "bê",
            "cê",
            "dê",
            "é",
            "éfe",
            "gê",
            "agá",
            "í",
            "jota",
            "cá",
            "éle",
            "ême",
            "ene",
            "ó",
            "pê",
            "quê",
            "érre",
            "ésse",
            "tê",
            "u",
            "vê",
            "dáblio",
            "xis",
            "ípsilon",
            "zê",
        ],
    )
)


def _ate_mil(n: int) -> str:
    if n < 20:
        return UNIDADES[n]
    if n < 100:
        return DEZENAS[n // 10] + ("" if n % 10 == 0 else " e " + UNIDADES[n % 10])
    if n == 100:
        return "cem"
    return CENTENAS[n // 100] + ("" if n % 100 == 0 else " e " + _ate_mil(n % 100))


def extenso(n: int, feminino: bool = False) -> str:
    """Integer in words, pt-BR (to the trillions)."""
    if n < 0:
        return "menos " + extenso(-n, feminino)
    if n == 0:
        return "zero"
    partes = []
    for valor, sing, plur in (
        (10**12, "trilhão", "trilhões"),
        (10**9, "bilhão", "bilhões"),
        (10**6, "milhão", "milhões"),
    ):
        if n >= valor:
            q, n = divmod(n, valor)
            partes.append(f"{extenso(q)} {sing if q == 1 else plur}")
    if n >= 1000:
        q, n = divmod(n, 1000)
        partes.append("mil" if q == 1 else f"{_ate_mil(q)} mil")
    if n:
        partes.append(_ate_mil(n))
    # "e" joins the last group when it is < 100 or a round hundred: "mil e cem", "dois mil e cinco".
    texto = partes[0]
    for parte, resto in zip(partes[1:], [n] * len(partes[1:]), strict=True):
        texto += (
            " e " if parte == partes[-1] and (resto < 100 or resto % 100 == 0) else " "
        ) + parte
    if feminino:
        texto = " ".join(FEM.get(w, w) for w in texto.split())
    return texto


def _decimal(texto_inteiro: str, fracao: str, feminino: bool = False) -> str:
    inteiro = int(texto_inteiro.replace(".", ""))
    fracao = fracao.rstrip("0")
    if not fracao:
        return extenso(inteiro, feminino)
    casa = (
        extenso(int(fracao))
        if not fracao.startswith("0")
        else " ".join(UNIDADES[int(d)] for d in fracao)
    )
    return f"{extenso(inteiro, feminino)} vírgula {casa}"


UNIDADES_MEDIDA = {
    "GB": ("gigabyte", "gigabytes"),
    "MB": ("megabyte", "megabytes"),
    "KB": ("kilobyte", "kilobytes"),
    "TB": ("terabyte", "terabytes"),
    "ms": ("milissegundo", "milissegundos"),
    "mm": ("milímetro", "milímetros"),
    "cm": ("centímetro", "centímetros"),
    "km": ("quilômetro", "quilômetros"),
    "kg": ("quilo", "quilos"),
    "g": ("grama", "gramas"),
    "W": ("watt", "watts"),
    "GHz": ("gigahertz", "gigahertz"),
    "MHz": ("megahertz", "megahertz"),
    "Hz": ("hertz", "hertz"),
    "s": ("segundo", "segundos"),
    "min": ("minuto", "minutos"),
    "h": ("hora", "horas"),
}


def _numero_com_unidade(m: re.Match[str]) -> str:
    inteiro, fracao, unidade = m.group(1), m.group(2) or "", m.group(3)
    sing, plur = UNIDADES_MEDIDA[unidade]
    fem = unidade in ("h", "g")  # "uma hora", "duas gramas" (coloquial: gramas fem.)
    valor = (
        _decimal(inteiro, fracao, fem) if fracao else extenso(int(inteiro.replace(".", "")), fem)
    )
    um = not fracao and int(inteiro.replace(".", "")) == 1
    return f"{valor} {sing if um else plur}"


# File extensions as Cadu should say them ("app.tsx" -> "app ponto tê esse xis").
EXTENSOES = {
    "py": "pai",
    "js": "jota esse",
    "mjs": "eme jota esse",
    "ts": "tê esse",
    "tsx": "tê esse xis",
    "jsx": "jota esse xis",
    "json": "jêison",
    "md": "eme dê",
    "html": "agá tê eme ele",
    "css": "cê esse esse",
    "sh": "esse agá",
    "yaml": "iâmel",
    "yml": "iâmel",
    "toml": "tômel",
    "txt": "tê xis tê",
    "csv": "cê esse vê",
    "log": "log",
    "db": "dê bê",
    "sql": "esse quê ele",
    "go": "gô",
    "rs": "erre esse",
    "service": "service",
    "conf": "conf",
    "glb": "gê ele bê",
    "gltf": "gê ele tê éfe",
    "stl": "esse tê ele",
    "3mf": "três eme éfe",
    "blend": "blend",
    "png": "pê ene gê",
    "jpg": "jota pê gê",
    "svg": "esse vê gê",
    "pdf": "pê dê éfe",
    "wav": "uav",
    "mp3": "eme pê três",
    "patch": "patch",
    "lock": "lock",
    "env": "env",
    "ini": "ini",
    "xml": "xis eme ele",
    "onnx": "ônix",
}
_EXT = "|".join(sorted(map(re.escape, EXTENSOES), key=len, reverse=True))
_DATA_ANTES = re.compile(r"(?:\b(?:dia|em|de|desde|até|para|no|hoje|amanhã|ontem|data)\s*)$", re.I)


def _nome_arquivo(segmento: str, linha: str | None = None) -> str:
    nome, ponto, ext = segmento.rpartition(".")
    if ponto and ext.lower() in EXTENSOES and nome:
        falado = (
            f"{nome.replace('_', ' ').replace('-', ' ').strip('. ')} ponto {EXTENSOES[ext.lower()]}"
        )
    else:
        falado = segmento.replace("_", " ").replace("-", " ")
    return falado + (f", linha {linha}" if linha else "")


def _caminho(m: re.Match[str]) -> str:
    caminho, linha = m["caminho"], m["linha"]
    partes = [p for p in caminho.split("/") if p not in ("", "~", ".", "..")]
    eh_caminho = (
        caminho[0] in "~./"
        or caminho.count("/") >= 2
        or re.search(rf"\.(?:{_EXT})$", caminho, re.I)
    ) and any(re.search("[A-Za-z]", p) for p in partes)
    return _nome_arquivo(partes[-1], linha) if eh_caminho and partes else m[0]


def _data_ou_fracao(m: re.Match[str]) -> str:
    a, b = int(m[1]), int(m[2])
    data = (
        (m[1].startswith("0") or m[2].startswith("0") or _DATA_ANTES.search(m.string[: m.start()]))
        and 1 <= a <= 31
        and 1 <= b <= 12
    )
    if data:
        return f"{'primeiro' if a == 1 else extenso(a)} de {MESES[b - 1]}"
    return f"{m[1]} de {m[2]}"


def _versao(m: re.Match[str]) -> str:
    grupos = m["num"].split(".")
    if not m["v"] and all(len(g) == 3 for g in grupos[1:]):
        return m[0]  # 1.234.567 is a thousands separator
    return ("versão " if m["v"] else "") + " ponto ".join(
        extenso(int(g)) if len(g) < 16 else g for g in grupos
    )


def tecnico(t: str) -> str:
    """Paths, hashes, versions, addresses, fractions and symbols -> words (before the numbers)."""
    t = re.sub(
        r"(?<![\w/@])(?P<caminho>"
        r"(?=[~\w@.+-]*/)(?:~|\.{1,2})?/?(?:[\w@.+-]+/)*[\w@.+-]*)(?::(?P<linha>\d+))?",
        _caminho,
        t,
    )  # paths first: a UUID inside one must not split it
    t = re.sub(
        rf"(?<![\w/])([\w-]+\.(?:{_EXT}))(?::(\d+))?\b",
        lambda m: _nome_arquivo(m[1], m[2]),
        t,
        flags=re.I,
    )
    t = re.sub(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "", t, flags=re.I
    )  # UUIDs
    t = re.sub(r"\b(commit|hash|sha|revisão)\s+#?[0-9a-f]{7,40}\b", r"\1", t, flags=re.I)
    t = re.sub(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b", "", t)  # bare hashes
    t = re.sub(r"\b((?:\d{1,3}\.){3}\d{1,3}|localhost):(\d{2,5})\b", r"\1, porta \2", t)
    t = re.sub(r"\be/ou\b", "e ou", t)
    t = re.sub(
        r"(?<![\w.])(?P<v>[vV](?=\d))?(?P<num>\d+(?:\.\d+){1,3})(?![\w.]*\d)(?!,\d)", _versao, t
    )
    t = re.sub(r"\b(\d+(?:,\d+)?)\s?[x×](?!\s?\d)(?![\w])", r"\1 vezes", t)
    t = re.sub(r"(?:\bn[º°o]\.?|#)\s?(\d+)\b", r"\1", t)
    t = re.sub(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])", _data_ou_fracao, t)
    t = re.sub(r"(?<=[A-Za-zÀ-ú])/(?=[A-Za-zÀ-ú])", " ou ", t)
    t = re.sub(r"(?<=\d)\s?@\s?(?=\d)", " a ", t)
    t = re.sub(r"(?<=\w)_(?=\w)", " ", t)
    for simbolo, fala in (
        ("≥", " pelo menos "),
        ("≤", " no máximo "),
        ("#", " "),
        ("@", " arroba "),
    ):
        t = t.replace(simbolo, fala)
    return re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"([,(]\s*)+(?=[,)])", "", " ".join(t.split())))


def falavel(texto: str) -> str:
    """Rewrite numbers and symbols so Cadu says them naturally. Idempotent on words."""
    t = str(texto)
    # Full dates first: "06/10/2026" and "2026-10-06" must not be read as fractions or versions.
    t = re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", lambda m: f"{m[3]}/{m[2]}/{m[1]}", t)
    t = re.sub(
        r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
        lambda m: (
            f"{'primeiro' if int(m[1]) == 1 else extenso(int(m[1]))} de {MESES[int(m[2]) - 1]}"
            f" de {extenso(int(m[3]))}"
            if 1 <= int(m[2]) <= 12
            else m[0]
        ),
        t,
    )
    t = tecnico(t)
    # Times hh:mm (before generic numbers).
    t = re.sub(
        r"\b([01]?\d|2[0-3])[:h]([0-5]\d)\b(?!\s*(?:GB|MB|ms))",
        lambda m: (
            f"{extenso(int(m[1]), True)} hora{'s' if int(m[1]) != 1 else ''}"
            + (
                ""
                if m[2] == "00"
                else f" e {extenso(int(m[2]))} minuto{'s' if int(m[2]) != 1 else ''}"
            )
        ),
        t,
    )
    # Money, percent, degrees, ordinals.
    t = re.sub(
        r"R\$\s?(\d[\d.]*)(?:,(\d{2}))?",
        lambda m: (
            f"{extenso(int(m[1].replace('.', '')))} rea{'l' if m[1] == '1' else 'is'}"
            + (f" e {extenso(int(m[2]))} centavos" if m[2] and m[2] != "00" else "")
        ),
        t,
    )
    t = re.sub(r"(\d[\d.]*)(?:,(\d+))?\s?%", lambda m: _decimal(m[1], m[2] or "") + " por cento", t)
    t = re.sub(
        r"(-?\d+)(?:,(\d+))?\s?°\s?C\b",
        lambda m: (
            ("menos " if m[1].startswith("-") else "")
            + _decimal(m[1].lstrip("-"), m[2] or "")
            + " graus Celsius"
        ),
        t,
    )
    t = re.sub(
        r"\b(\d{1,2})\s?[ºª°]",
        lambda m: (
            ORD.get(int(m[1]), extenso(int(m[1])))
            if m[0].strip()[-1] != "ª"
            else ORD.get(int(m[1]), extenso(int(m[1])))[:-1] + "a"
        ),
        t,
    )
    # Dimensions "100 x 47" / "100 mm x 47 mm" (before units turn digits into words).
    t = re.sub(r"(?<=\d)(\s?[a-zA-Z]{0,3})\s?[x×]\s?(?=\d)", r"\1 por ", t)
    # Numbers with units (3,5 GB / 100 mm / 15 ms).
    unidades = "|".join(sorted(UNIDADES_MEDIDA, key=len, reverse=True))
    t = re.sub(rf"\b(\d[\d.]*)(?:,(\d+))?\s?({unidades})\b", _numero_com_unidade, t)
    # Ranges and symbols between numbers.
    t = re.sub(r"(\d)\s?[–-]\s?(\d)", r"\1 a \2", t)
    t = (
        t.replace("→", " para ")
        .replace("->", " para ")
        .replace("≈", "cerca de ")
        .replace("~", "cerca de ")
        .replace("+", " mais ")
        .replace("&", " e ")
    )
    # Remaining decimals (3,5 / 1.234) and integers.
    t = re.sub(r"\b(\d{1,3}(?:\.\d{3})+|\d+),(\d+)\b", lambda m: _decimal(m[1], m[2]), t)
    t = re.sub(r"\b\d{1,3}(?:\.\d{3})+\b", lambda m: extenso(int(m[0].replace(".", ""))), t)
    # Number glued to one letter ("4b", "2a"): the letter is said by its name.
    t = re.sub(
        r"\b(\d{1,3})([A-Za-z])\b", lambda m: f"{extenso(int(m[1]))} {LETRAS[m[2].lower()]}", t
    )
    # Concordância: "1 hora" é "uma hora", "2 semanas" é "duas semanas" (teste de 06/10/2026).
    t = re.sub(
        rf"\b(\d+)(\s+(?:{FEMININAS})\b)",
        lambda m: extenso(int(m[1]), True) + m[2] if len(m[1]) <= 15 else m[0],
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"\b\d+\b", lambda m: extenso(int(m[0])) if len(m[0]) <= 15 else m[0], t)
    return " ".join(t.split())


# A pesquisa na internet (WebSearch) obriga o modelo a fechar com "Fontes:" e uma lista de links;
# falada, a lista virou um minuto de títulos (teste de 08/10/2026). Ela vai para a tela.
_FONTES = re.compile(r"(?im)^[ \t]*[*_]*(?:fontes|sources|referências)[*_]*[ \t]*:")


def separar_fontes(texto: str) -> tuple[str, str]:
    """("o que se fala", "Fontes: ...") de um pedaço da resposta; sem fontes, (texto, "")."""
    m = _FONTES.search(texto)
    if not m:
        return texto, ""
    return texto[: m.start()], texto[m.start() :].strip()


def para_fala(texto: str, limite: int = 2400) -> str:
    """Markdown/code/URLs out; long answers cut at a sentence. O JARVIS novo não tem chat: as
    frases antigas ("disponível no chat") viraram referências neutras (teste de 06/10/2026)."""
    value = re.sub(r"```.*?```", " um trecho de código. ", str(texto), flags=re.S)
    value = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"https?://\S+", " o link ", value)
    # Short inline code is a name ("listener.py", "npm test"): say it; long code goes to the chat.
    value = re.sub(
        r"`([^`]+)`",
        lambda m: m[1] if len(m[1]) <= 40 else " um trecho técnico ",
        value,
    )
    value = re.sub(r"^\s*(?:#{1,6}\s+|>\s*|[-*+]\s+|\d+[.)]\s+)", "", value, flags=re.M)
    value = re.sub(r"\*\*|__|~~", "", value)
    value = re.sub(r"[|*]", " ", value)  # "~" and "_" stay: home paths, "about", file names
    value = " ".join(value.split())
    if len(value) > limite:
        head = value[: limite - 100]
        end = max(head.rfind(". "), head.rfind("! "), head.rfind("? "))
        value = (
            head[: end + 1] if end > 1000 else head.rsplit(" ", 1)[0]
        ) + " Tem mais; se quiser, eu continuo."
    return value
