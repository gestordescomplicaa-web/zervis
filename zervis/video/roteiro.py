"""O plano de direção de um vídeo (ADR 0106 e 0107): o modelo dirige, num formato fechado, e o Zé
confere.

O modelo nunca escreve HTML nem código. Ele pensa como diretor: define o objetivo e o público,
divide a fala em cenas e, para cada uma, escolhe o tipo, a composição, o movimento de câmera, a
transição e em que palavra da fala cada elemento entra. Aqui tudo é conferido, cortado nos limites
e só então vai para a página (que mostra o texto como texto). Uma cena fora do formato derruba o
plano: ele volta uma vez ao modelo com o motivo.

**A tela não repete a fala.** Nas cenas de texto (gancho e frase) a própria fala é a tipografia,
palavra por palavra, no tempo da voz; nas cenas visuais, a legenda acompanha embaixo e a tela
mostra só a ideia, em poucas palavras.
"""

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from zervis.marketing_visual import icones as icones_da_marca
from zervis.video.estilos import Estilo

FALA_PALAVRAS = 22
PALAVRAS_POR_SEGUNDO = 2.9  # o ritmo medido da voz do Zé (Fish Audio): 95 palavras em 33 s
LIMITE_LEGENDA = 2200
# A duração pedida -> (mínimo, máximo) de cenas.
DURACOES: dict[int, tuple[int, int]] = {15: (3, 4), 30: (4, 7), 45: (6, 9), 60: (7, 11)}
DURACAO_PADRAO = 30
CAMERAS = ("empurra", "afasta", "desliza", "parado")
TRANSICOES = ("corte", "mascara", "deslize", "zoom", "cor")
DE_TEXTO = ("gancho", "frase")  # a fala é a tipografia; sem legenda embaixo

# Cada tipo: os campos de texto (com o limite), as listas (mínimo, máximo, limite de cada item),
# as composições e o que o modelo lê sobre ele.
TIPOS: dict[str, dict[str, Any]] = {
    "gancho": {
        "textos": {"rotulo": 28, "destaque": 40},
        "composicoes": ("centro", "esquerda", "gigante"),
        "formato": '{"tipo": "gancho", "fala": "...", "destaque": "1 a 3 palavras da fala em cor", '
        '"rotulo": "opcional, até 28 (o assunto, em cápsula)", "composicao": '
        '"centro|esquerda|gigante"} (a fala aparece inteira na tela, animada; não escreva outro '
        'texto; "gigante" é uma palavra por linha, enorme: só para falas de até 7 palavras)',
    },
    "frase": {
        "textos": {"destaque": 40},
        "composicoes": ("centro", "esquerda", "cheia"),
        "formato": '{"tipo": "frase", "fala": "...", "destaque": "...", '
        '"composicao": "centro|esquerda|cheia"} (a fala vira a tipografia; para uma afirmação '
        'forte; "cheia" pinta a tela inteira com a cor da marca: use uma vez, no momento-chave)',
    },
    "passos": {
        "textos": {"titulo": 32},
        "listas": {"passos": (2, 4, 38)},
        "composicoes": ("vertical",),
        "formato": '{"tipo": "passos", "fala": "...", "titulo": "até 32, sem repetir a fala", '
        '"passos": [{"texto": "até 38", "quando": "a palavra da fala em que ele entra"}]} '
        "(2 a 4)",
    },
    "antes_depois": {
        "textos": {"titulo": 32, "antes": 60, "depois": 60, "quando": 30},
        "composicoes": ("empilhado", "dividido"),
        "formato": '{"tipo": "antes_depois", "fala": "...", "antes": "até 60", '
        '"depois": "até 60", "quando": "a palavra da fala em que o depois entra", '
        '"composicao": "empilhado|dividido"}',
    },
    "conversa": {
        "mensagens": (2, 4, 70),
        "composicoes": ("janela",),
        "formato": '{"tipo": "conversa", "fala": "...", "mensagens": [{"de": "cliente" ou '
        '"empresa", "texto": "até 70", "quando": "palavra da fala"}]} (2 a 4; sempre um '
        "exemplo, nunca uma conversa real)",
    },
    "lista": {
        "textos": {"titulo": 32},
        "listas": {"itens": (2, 4, 32)},
        "composicoes": ("cartoes", "um_por_vez"),
        "formato": '{"tipo": "lista", "fala": "...", "titulo": "até 32", "itens": [{"texto": '
        '"até 32", "quando": "palavra da fala"}], "composicao": "cartoes|um_por_vez"} (2 a 4)',
    },
    "numero": {
        "textos": {"valor": 10, "rotulo": 60, "fonte": 60},
        "obrigatorios": ("valor", "rotulo", "fonte"),
        "composicoes": ("anel", "gigante"),
        "formato": '{"tipo": "numero", "fala": "...", "valor": "87%", "rotulo": "o que o número '
        'diz (até 60)", "fonte": "de onde veio", "composicao": "anel|gigante"} (só com um '
        "número do material, com a fonte)",
    },
    # --- as cenas de arte (ADR 0110): a ideia em ícones e movimento, a fala na legenda ---
    "icone": {
        "textos": {"rotulo": 22, "quando": 30},
        "icones": ("icone",),
        "composicoes": ("heroi",),
        "formato": '{"tipo": "icone", "fala": "...", "icone": "<um da lista>", "rotulo": '
        '"opcional, 1 a 3 palavras", "quando": "a palavra da fala em que ele se desenha"} (um '
        "conceito: o ícone enorme se desenha, ondas e faíscas saem dele)",
    },
    "conexao": {
        "nos": (2, 4, 16),
        "composicoes": ("fluxo",),
        "formato": '{"tipo": "conexao", "fala": "...", "nos": [{"icone": "<da lista>", '
        '"rotulo": "1 ou 2 palavras", "quando": "palavra da fala"}]} (2 a 4: um fluxo ou uma '
        "integração; linhas ligam os nós e dados correm por elas)",
    },
    "hub": {
        "nos": (3, 6, 16),
        "campo_nos": "ao_redor",
        "composicoes": ("orbita",),
        "formato": '{"tipo": "hub", "fala": "...", "centro": {"icone": "<da lista> ou marca", '
        '"rotulo": "opcional"}, "ao_redor": [{"icone": "<da lista>", "rotulo": "opcional, 1 '
        'palavra", "quando": "palavra da fala"}]} (3 a 6 em volta de um centro: tudo ligado a '
        'uma coisa só; a marca no centro com "marca")',
    },
    "caos": {
        "textos": {"rotulo": 26, "quando": 30},
        "composicoes": ("grade",),
        "formato": '{"tipo": "caos", "fala": "...", "icones": ["4 a 9 da lista"], "rotulo": '
        '"opcional, o que a ordem significa", "quando": "a palavra da fala em que tudo se '
        'organiza"} (o problema virando solução: ícones espalhados e tremendo se alinham)',
    },
    "fecho": {
        "textos": {"chamada": 32, "detalhe": 32},
        "obrigatorios": ("chamada",),
        "composicoes": ("marca",),
        "formato": '{"tipo": "fecho", "fala": "...", "chamada": "o convite, até 32", '
        '"detalhe": "opcional (por exemplo, Link na bio)"}',
    },
}
for _regra in TIPOS.values():
    _regra.setdefault("obrigatorios", tuple(_regra.get("listas", {})) or ())
DE_ARTE = ("icone", "conexao", "hub", "caos")
DE_CARTAO = ("passos", "lista", "antes_depois", "conversa")

PROMPT = """Você é o diretor de criação de um Reels (vídeo vertical, cerca de {duracao} segundos)
para {marca}. Pense como roteirista, motion designer e editor: o vídeo precisa parecer feito por
uma equipe de audiovisual, nunca uma apresentação de slides.

{pedido}

Primeiro decida o objetivo (o que quem assiste deve pensar ou fazer no fim) e o público. Depois
escreva a fala do vídeo inteiro e divida em cenas; cada cena tem um papel só (prender, explicar,
provar, convidar) e um jeito de mostrar.

Responda só com JSON, sem texto em volta:
{{"objetivo": "...", "publico": "...", "titulo": "...", "legenda": "...",
"cenas": [{{"tipo": "...", "fala": "...", "camera": "...", "transicao": "...", ...}}]}}

O limite mais importante: **a fala inteira tem de {minimo_palavras} a {total} palavras**. Conte
antes de responder; passou, corte. Um bom Reels diz pouco e mostra muito.

Regras:
- De {minimo} a {maximo} cenas. A primeira é um "gancho" (a frase que faz parar de rolar, nos
  dois primeiros segundos); a última, um "fecho".
- fala: português do Brasil falado, uma ou duas frases curtas, até {fala} palavras. Sem siglas
  difíceis de falar e sem emojis. Números como se fala ("treze de novembro").
- **A tela não repete a fala.** Em "gancho" e "frase" a própria fala aparece animada; não escreva
  outro texto. Nas outras cenas, a legenda já mostra a fala: a tela mostra só a ideia, em poucas
  palavras (títulos e itens curtos, diferentes da fala).
- quando: a palavra da fala daquela cena (exatamente como escrita nela) em que o elemento entra;
  assim a tela acompanha a voz. Use palavras diferentes para elementos diferentes.
- camera: {cameras}. "empurra" é um soco de câmera na palavra de destaque (dê um destaque à
  cena); "afasta" e "desliza" mexem só na chegada; "parado" não mexe.
- transicao (como a cena entra): {transicoes}. "mascara" abre um círculo a partir do que estava
  em foco; "deslize" é um chicote rápido para o lado; "zoom" atravessa o que estava em foco; "cor"
  inunda a tela com a cor da marca (para mudar de assunto); "corte" é seco, na batida. Use 3 a 5
  tipos no vídeo e nunca a mesma transição em cenas seguidas; "corte" nos momentos de impacto.
- **Mostre, não escreva.** Pelo menos metade das cenas entre o gancho e o fecho são de arte
  (icone, conexao, hub, caos): a ideia vira um ícone que se desenha, um fluxo por onde correm
  dados, uma constelação em volta de um centro, o caos que vira ordem. Cartões de texto (passos,
  lista, antes_depois, conversa) no máximo dois no vídeo. Pense numa analogia para cada ideia.
- Varie os tipos e as composições. No máximo um "frase" seguido de outro tipo de texto.
- Não invente números, casos, clientes nem depoimentos. "numero" só com um dado do material,
  com a fonte. Uma "conversa" é sempre um exemplo.
- titulo: até 60 caracteres. legenda: a do Instagram, de 300 a 1.000 caracteres, com o gancho, a
  explicação em parágrafos curtos, a chamada, no máximo 3 emojis e até 5 hashtags no fim.
{tom}
Tipos de cena:
{tipos}

Ícones (use só estes nomes): {icones}

## Linha editorial (o manual do site)
{manual}
"""


class RoteiroErro(ValueError):
    """O plano não veio no formato; a mensagem vai para a tela (e para o modelo, na volta)."""


@dataclass
class Roteiro:
    titulo: str
    legenda: str
    cenas: list[dict[str, Any]] = field(default_factory=list)
    objetivo: str = ""
    publico: str = ""

    @property
    def falas(self) -> list[str]:
        return [str(c["fala"]) for c in self.cenas]

    def para_json(self) -> dict[str, Any]:
        return {
            "objetivo": self.objetivo,
            "publico": self.publico,
            "titulo": self.titulo,
            "legenda": self.legenda,
            "cenas": self.cenas,
        }


def base(palavra: str) -> str:
    """A palavra sem acento, pontuação nem maiúscula: para casar o "quando" com a fala."""
    sem_acento = unicodedata.normalize("NFKD", palavra).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def _texto(valor: Any, limite: int) -> str:
    texto = " ".join(str(valor or "").split())
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def limites(duracao: int) -> tuple[int, int, int, int]:
    """(mínimo e máximo de cenas, mínimo e máximo de palavras da fala) para a duração."""
    minimo, maximo = DURACOES.get(duracao, DURACOES[DURACAO_PADRAO])
    total = round(duracao * PALAVRAS_POR_SEGUNDO)
    return minimo, maximo, round(total * 0.6), total


def tipos_do_estilo(estilo: Estilo) -> dict[str, str]:
    """O formato de cada tipo de cena para o modelo: os embutidos e os que o estilo acrescenta."""
    extras = {t: f if t in f else f"{t}: {f}" for t, f in estilo.cenas_extras.items()}
    return {**{t: d["formato"] for t, d in TIPOS.items()}, **extras}


def montar_prompt(
    marca: str, pedido: str, manual: str, estilo: Estilo, duracao: int = DURACAO_PADRAO
) -> str:
    minimo, maximo, minimo_palavras, total = limites(duracao)
    return PROMPT.format(
        duracao=duracao,
        marca=marca or "uma empresa",
        pedido=pedido,
        minimo=minimo,
        maximo=maximo,
        minimo_palavras=minimo_palavras,
        total=total,
        fala=FALA_PALAVRAS,
        cameras=" | ".join(CAMERAS),
        transicoes=" | ".join(TRANSICOES),
        tom=f"- Tom: {estilo.tom}\n" if estilo.tom else "",
        tipos="\n".join(f"- {formato}" for formato in tipos_do_estilo(estilo).values()),
        icones=", ".join(sorted(icones_da_marca())),
        manual=manual or "(o site não tem manual; use um tom profissional, claro e direto)",
    )


def _icone(nome: Any) -> str:
    """Um ícone da lista; um nome que não existe vira "sparkles" (nunca um desenho do modelo)."""
    nome = str(nome or "").strip().lower()
    return nome if nome in icones_da_marca() else "sparkles"


def icones_usados(cenas: list[dict[str, Any]]) -> set[str]:
    nomes: set[str] = set()
    for c in cenas:
        if isinstance(c.get("icone"), str):
            nomes.add(c["icone"])
        for campo in ("nos", "ao_redor"):
            nomes.update(str(x.get("icone", "")) for x in c.get(campo) or [])
        if isinstance(c.get("centro"), dict):
            nomes.add(str(c["centro"].get("icone", "")))
        nomes.update(str(x) for x in c.get("icones") or [])
    return {n for n in nomes if n in icones_da_marca()}


def _quando(valor: Any, fala: str) -> str:
    """O "quando" só vale se a palavra está na fala da cena."""
    partes = str(valor or "").split()
    alvo = base(partes[0]) if partes else ""
    return alvo if alvo and any(base(p) == alvo for p in fala.split()) else ""


def _itens(bruta: Any, limite: int, fala: str) -> list[dict[str, str]]:
    """Uma lista de itens, como texto ou como {"texto", "quando"}."""
    saida = []
    for x in bruta if isinstance(bruta, list) else []:
        if isinstance(x, dict):
            texto, quando = _texto(x.get("texto"), limite), _quando(x.get("quando"), fala)
        elif isinstance(x, str):
            texto, quando = _texto(x, limite), ""
        else:
            continue
        if texto:
            saida.append({"texto": texto, "quando": quando})
    return saida


def _cena(bruta: Any, extras: dict[str, str]) -> dict[str, Any]:
    if not isinstance(bruta, dict):
        raise RoteiroErro("Uma cena veio fora do formato.")
    tipo = str(bruta.get("tipo", ""))
    fala = _texto(bruta.get("fala"), 200)
    if not fala:
        raise RoteiroErro("Uma cena veio sem fala.")
    if len(fala.split()) > FALA_PALAVRAS + 8:
        raise RoteiroErro(f"Uma fala ficou longa demais (até {FALA_PALAVRAS} palavras).")
    camera = str(bruta.get("camera", ""))
    transicao = str(bruta.get("transicao", ""))
    comum = {
        "tipo": tipo,
        "fala": fala,
        "camera": camera if camera in CAMERAS else "empurra",
        "transicao": transicao if transicao in TRANSICOES else "zoom",
    }
    if tipo in extras and tipo not in TIPOS:
        # uma cena do estilo: só texto e listas de texto, cortados
        cena: dict[str, Any] = dict(comum)
        for k, v in bruta.items():
            if k in cena or not re.fullmatch(r"[a-z_]{1,24}", str(k)):
                continue
            if isinstance(v, list):
                cena[k] = [_texto(x, 120) for x in v[:6] if isinstance(x, (str, int, float))]
            elif isinstance(v, (str, int, float)):
                cena[k] = _texto(v, 200)
        return cena
    regra = TIPOS.get(tipo)
    if regra is None:
        raise RoteiroErro(f"Tipo de cena desconhecido: {tipo or 'vazio'}.")
    cena = dict(comum)
    composicao = str(bruta.get("composicao", ""))
    composicoes = regra["composicoes"]
    cena["composicao"] = composicao if composicao in composicoes else composicoes[0]
    if cena["composicao"] == "gigante" and tipo == "gancho" and len(fala.split()) > 7:
        cena["composicao"] = "centro"  # uma palavra por linha só cabe com fala curta
    for campo, limite in regra.get("textos", {}).items():
        if valor := _texto(bruta.get(campo), limite):
            cena[campo] = valor
    if "quando" in cena:
        cena["quando"] = _quando(cena["quando"], fala)
    for campo, (minimo, maximo, limite) in regra.get("listas", {}).items():
        itens = _itens(bruta.get(campo), limite, fala)[:maximo]
        if len(itens) < minimo:
            raise RoteiroErro(f"A cena {tipo} precisa de pelo menos {minimo} itens.")
        cena[campo] = itens
    if "mensagens" in regra:
        minimo, maximo, limite = regra["mensagens"]
        msgs = [
            {
                "de": "cliente" if m.get("de") == "cliente" else "empresa",
                "texto": _texto(m.get("texto"), limite),
                "quando": _quando(m.get("quando"), fala),
            }
            for m in (bruta.get("mensagens") or [])
            if isinstance(m, dict) and str(m.get("texto", "")).strip()
        ][:maximo]
        if len(msgs) < minimo:
            raise RoteiroErro("A conversa precisa de pelo menos 2 mensagens.")
        cena["mensagens"] = msgs
    if "icones" in regra:
        cena["icone"] = _icone(bruta.get("icone"))
    if "nos" in regra:
        minimo, maximo, limite = regra["nos"]
        campo = regra.get("campo_nos", "nos")
        nos = [
            {
                "icone": _icone(x.get("icone")),
                "rotulo": _texto(x.get("rotulo"), limite),
                "quando": _quando(x.get("quando"), fala),
            }
            for x in (bruta.get(campo) or [])
            if isinstance(x, dict)
        ][:maximo]
        if len(nos) < minimo:
            raise RoteiroErro(f"A cena {tipo} precisa de pelo menos {minimo} nós.")
        cena[campo] = nos
        if tipo == "hub":
            centro: dict[str, Any] = (
                bruta["centro"] if isinstance(bruta.get("centro"), dict) else {}
            )
            marca = str(centro.get("icone", "")) == "marca"
            cena["centro"] = {
                "icone": "marca" if marca else _icone(centro.get("icone")),
                "rotulo": _texto(centro.get("rotulo"), limite),
            }
    if tipo == "caos":
        nomes = [_icone(x) for x in (bruta.get("icones") or []) if isinstance(x, str)][:9]
        if len(nomes) < 4:
            raise RoteiroErro("A cena caos precisa de pelo menos 4 ícones.")
        cena["icones"] = nomes
    if tipo == "numero" and not re.search(r"\d", cena.get("valor", "")):
        raise RoteiroErro("O número da cena não tem número.")
    faltando = [c for c in regra["obrigatorios"] if not cena.get(c)]
    if faltando:
        raise RoteiroErro(f"A cena {tipo} veio sem {', '.join(faltando)}.")
    if tipo == "antes_depois" and not (cena.get("antes") and cena.get("depois")):
        raise RoteiroErro("A cena antes_depois veio sem o antes ou o depois.")
    return cena


def interpretar(resposta: str, estilo: Estilo, duracao: int = DURACAO_PADRAO) -> Roteiro:
    """O JSON do modelo, conferido. Aceita o JSON cercado por texto ou bloco de código."""
    minimo, maximo, _, total = limites(duracao)
    achado = re.search(r"\{.*\}", resposta, re.S)
    if not achado:
        raise RoteiroErro("O modelo não devolveu um roteiro.")
    try:
        dados = json.loads(achado.group(0))
    except ValueError as erro:
        raise RoteiroErro("O roteiro veio com JSON inválido.") from erro
    brutas = dados.get("cenas") if isinstance(dados, dict) else None
    if not isinstance(brutas, list) or not minimo <= len(brutas) <= maximo:
        raise RoteiroErro(f"O roteiro precisa de {minimo} a {maximo} cenas.")
    cenas = [_cena(c, estilo.cenas_extras) for c in brutas]
    if cenas[0]["tipo"] != "gancho" or cenas[-1]["tipo"] != "fecho":
        raise RoteiroErro("O roteiro precisa começar com um gancho e terminar com um fecho.")
    palavras = sum(len(c["fala"].split()) for c in cenas)
    if palavras > total + 10:
        raise RoteiroErro(
            f"A fala ficou longa demais para {duracao} s ({palavras} palavras; até {total}). "
            f"Corte {palavras - total} palavras ou mais: frases mais curtas e, se precisar, uma "
            "cena a menos."
        )
    titulo = _texto(dados.get("titulo"), 60) or _texto(cenas[0]["fala"], 60)
    return Roteiro(
        titulo,
        str(dados.get("legenda") or "").strip()[:LIMITE_LEGENDA],
        cenas,
        _texto(dados.get("objetivo"), 200),
        _texto(dados.get("publico"), 200),
    )


def tempos_dos_gatilhos(cena: dict[str, Any], palavras: list[dict[str, Any]]) -> dict[str, Any]:
    """Os "quando" da cena em segundos desde o começo dela (`tempos_<lista>` e `tempo`, do depois),
    pelo tempo real das palavras. O que não tem "quando" fica None: a página distribui no tempo
    da cena."""
    inicio = float(cena["inicio"])

    def achar(alvo: str) -> float | None:
        if not alvo:
            return None
        for p in palavras:
            if base(str(p["p"])) == alvo:
                return round(max(0.0, float(p["i"]) - inicio), 3)
        return None

    saida: dict[str, Any] = {}
    for campo in ("passos", "itens", "mensagens", "nos", "ao_redor"):
        if campo in cena:
            saida[f"tempos_{campo}"] = [achar(str(x.get("quando", ""))) for x in cena[campo]]
    if cena.get("quando"):
        saida["tempo"] = achar(str(cena["quando"]))
    return saida
