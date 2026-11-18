"""O roteiro de um vídeo (ADR 0106): o modelo escreve, num formato fechado, e o Zé confere.

O modelo nunca escreve HTML nem código: escolhe o tipo de cada cena, escreve o texto da tela e a
fala do Zé. Aqui tudo é conferido, cortado nos limites e só então vai para a página (que mostra o
texto como texto). Uma cena fora do formato derruba o roteiro: melhor pedir de novo do que
mostrar um vídeo quebrado.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any

from zervis.video.estilos import Estilo

MINIMO_CENAS, MAXIMO_CENAS = 4, 7
FALA_PALAVRAS, TOTAL_PALAVRAS = 20, 80  # ~2,6 palavras por segundo: uns 25 s de voz
LIMITE_LEGENDA = 2200

# Cada tipo: os campos de texto (com o limite), as listas (mínimo, máximo, limite de cada item) e
# o que o modelo lê sobre ele.
TIPOS: dict[str, dict[str, Any]] = {
    "gancho": {
        "textos": {"texto": 70, "destaque": 40, "rotulo": 28, "apoio": 90},
        "obrigatorios": ("texto",),
        "formato": '{"tipo": "gancho", "texto": "a frase que faz parar de rolar (até 70)", '
        '"destaque": "1 a 3 palavras do texto em cor", "rotulo": "opcional, até 28", '
        '"apoio": "opcional, até 90"}',
    },
    "frase": {
        "textos": {"texto": 110, "destaque": 40},
        "obrigatorios": ("texto",),
        "formato": '{"tipo": "frase", "texto": "uma afirmação forte (até 110)", "destaque": "..."}',
    },
    "passos": {
        "textos": {"titulo": 40},
        "listas": {"passos": (2, 4, 38)},
        "obrigatorios": ("titulo", "passos"),
        "formato": '{"tipo": "passos", "titulo": "até 40", "passos": ["2 a 4, até 38 cada"]}',
    },
    "antes_depois": {
        "textos": {
            "titulo": 40,
            "antes": 70,
            "depois": 70,
            "rotulo_antes": 14,
            "rotulo_depois": 14,
        },
        "obrigatorios": ("antes", "depois"),
        "formato": '{"tipo": "antes_depois", "titulo": "opcional", "antes": "até 70", '
        '"depois": "até 70"}',
    },
    "conversa": {
        "mensagens": (2, 4, 70),
        "obrigatorios": ("mensagens",),
        "formato": '{"tipo": "conversa", "mensagens": [{"de": "cliente" ou "empresa", '
        '"texto": "até 70"}]} (2 a 4; sempre um exemplo, nunca uma conversa real)',
    },
    "lista": {
        "textos": {"titulo": 40},
        "listas": {"itens": (2, 4, 36)},
        "obrigatorios": ("titulo", "itens"),
        "formato": '{"tipo": "lista", "titulo": "até 40", "itens": ["2 a 4, até 36 cada"]}',
    },
    "numero": {
        "textos": {"valor": 10, "rotulo": 70, "fonte": 60},
        "obrigatorios": ("valor", "rotulo", "fonte"),
        "formato": '{"tipo": "numero", "valor": "87%", "rotulo": "o que o número diz (até 70)", '
        '"fonte": "de onde veio (até 60)"} (só com um número do material, com a fonte)',
    },
    "fecho": {
        "textos": {"chamada": 36, "detalhe": 40},
        "obrigatorios": ("chamada",),
        "formato": '{"tipo": "fecho", "chamada": "o convite, até 36", "detalhe": "opcional, '
        'até 40 (por exemplo, Link na bio)"}',
    },
}

PROMPT = """Escreva o roteiro de um Reels (vídeo vertical, de 20 a 30 segundos) para {marca}.

O vídeo é narrado: cada cena tem uma fala, e a tela mostra o que a fala diz. É explicativo e
interessante: ensina uma coisa só, com começo forte e fim com convite.

{pedido}

Responda só com JSON, sem texto em volta:
{{"titulo": "...", "legenda": "...", "cenas": [{{"tipo": "...", "fala": "...", ...}}]}}

O limite mais importante: **a narração inteira tem de 50 a {total} palavras** (cerca de 25
segundos). Conte as palavras de todas as falas antes de responder; passou, corte. Um Reels bom diz
pouco e mostra muito.

Regras:
- De {minimo} a {maximo} cenas. A primeira é um "gancho"; a última, um "fecho".
- fala: o que a voz diz na cena, em português do Brasil falado: uma ou duas frases curtas, até
  {fala} palavras. Sem siglas difíceis de falar e sem emojis.
- A tela não repete a fala inteira: mostra a ideia em poucas palavras.
- Não invente números, casos, clientes nem depoimentos. "numero" só com um dado do material
  abaixo, com a fonte. Uma "conversa" é sempre um exemplo.
- Varie os tipos; use os que ajudam a entender.
- titulo: até 60 caracteres, para a lista de vídeos. legenda: a do Instagram, de 300 a 1.000
  caracteres, com o gancho, a explicação em parágrafos curtos, a chamada, no máximo 3 emojis e
  até 5 hashtags no fim.
{tom}
Tipos de cena:
{tipos}

## Linha editorial (o manual do site)
{manual}
"""


class RoteiroErro(ValueError):
    """O roteiro não veio no formato; a mensagem vai para a tela."""


@dataclass
class Roteiro:
    titulo: str
    legenda: str
    cenas: list[dict[str, Any]] = field(default_factory=list)

    @property
    def falas(self) -> list[str]:
        return [str(c["fala"]) for c in self.cenas]

    def para_json(self) -> dict[str, Any]:
        return {"titulo": self.titulo, "legenda": self.legenda, "cenas": self.cenas}


def _texto(valor: Any, limite: int) -> str:
    texto = " ".join(str(valor or "").split())
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def tipos_do_estilo(estilo: Estilo) -> dict[str, str]:
    """O formato de cada tipo de cena para o modelo: os embutidos e os que o estilo acrescenta."""
    extras = {t: f if t in f else f"{t}: {f}" for t, f in estilo.cenas_extras.items()}
    return {**{t: d["formato"] for t, d in TIPOS.items()}, **extras}


def montar_prompt(marca: str, pedido: str, manual: str, estilo: Estilo) -> str:
    tipos = tipos_do_estilo(estilo)
    return PROMPT.format(
        marca=marca or "uma empresa",
        pedido=pedido,
        minimo=MINIMO_CENAS,
        maximo=MAXIMO_CENAS,
        fala=FALA_PALAVRAS,
        total=TOTAL_PALAVRAS,
        tom=f"- Tom: {estilo.tom}\n" if estilo.tom else "",
        tipos="\n".join(f"- {formato}" for formato in tipos.values()),
        manual=manual or "(o site não tem manual; use um tom profissional, claro e direto)",
    )


def _cena(bruta: Any, extras: dict[str, str]) -> dict[str, Any]:
    if not isinstance(bruta, dict):
        raise RoteiroErro("Uma cena veio fora do formato.")
    tipo = str(bruta.get("tipo", ""))
    fala = _texto(bruta.get("fala"), 240)
    if not fala:
        raise RoteiroErro("Uma cena veio sem fala.")
    if len(fala.split()) > FALA_PALAVRAS + 8:
        raise RoteiroErro(f"Uma fala ficou longa demais (até {FALA_PALAVRAS} palavras).")
    if tipo in extras and tipo not in TIPOS:
        # uma cena do estilo: só texto e listas de texto, cortados
        cena: dict[str, Any] = {"tipo": tipo, "fala": fala}
        for k, v in bruta.items():
            if k in ("tipo", "fala") or not re.fullmatch(r"[a-z_]{1,24}", str(k)):
                continue
            if isinstance(v, list):
                cena[k] = [_texto(x, 120) for x in v[:6] if isinstance(x, (str, int, float))]
            elif isinstance(v, (str, int, float)):
                cena[k] = _texto(v, 200)
        return cena
    regra = TIPOS.get(tipo)
    if regra is None:
        raise RoteiroErro(f"Tipo de cena desconhecido: {tipo or 'vazio'}.")
    cena = {"tipo": tipo, "fala": fala}
    for campo, limite in regra.get("textos", {}).items():
        if valor := _texto(bruta.get(campo), limite):
            cena[campo] = valor
    for campo, (minimo, maximo, limite) in regra.get("listas", {}).items():
        itens = [_texto(x, limite) for x in (bruta.get(campo) or []) if isinstance(x, str)]
        itens = [x for x in itens if x][:maximo]
        if len(itens) < minimo:
            raise RoteiroErro(f"A cena {tipo} precisa de pelo menos {minimo} itens.")
        cena[campo] = itens
    if "mensagens" in regra:
        minimo, maximo, limite = regra["mensagens"]
        msgs = [
            {
                "de": "cliente" if m.get("de") == "cliente" else "empresa",
                "texto": _texto(m.get("texto"), limite),
            }
            for m in (bruta.get("mensagens") or [])
            if isinstance(m, dict) and str(m.get("texto", "")).strip()
        ][:maximo]
        if len(msgs) < minimo:
            raise RoteiroErro("A conversa precisa de pelo menos 2 mensagens.")
        cena["mensagens"] = msgs
    if tipo == "numero" and not re.search(r"\d", cena.get("valor", "")):
        raise RoteiroErro("O número da cena não tem número.")
    faltando = [c for c in regra.get("obrigatorios", ()) if not cena.get(c)]
    if faltando:
        raise RoteiroErro(f"A cena {tipo} veio sem {', '.join(faltando)}.")
    if "destaque" in bruta and "destaque" not in cena:
        cena["destaque"] = _texto(bruta.get("destaque"), 40)
    return cena


def interpretar(resposta: str, estilo: Estilo) -> Roteiro:
    """O JSON do modelo, conferido. Aceita o JSON cercado por texto ou bloco de código."""
    achado = re.search(r"\{.*\}", resposta, re.S)
    if not achado:
        raise RoteiroErro("O modelo não devolveu um roteiro.")
    try:
        dados = json.loads(achado.group(0))
    except ValueError as erro:
        raise RoteiroErro("O roteiro veio com JSON inválido.") from erro
    brutas = dados.get("cenas") if isinstance(dados, dict) else None
    if not isinstance(brutas, list) or not MINIMO_CENAS <= len(brutas) <= MAXIMO_CENAS:
        raise RoteiroErro(f"O roteiro precisa de {MINIMO_CENAS} a {MAXIMO_CENAS} cenas.")
    cenas = [_cena(c, estilo.cenas_extras) for c in brutas]
    if cenas[0]["tipo"] != "gancho" or cenas[-1]["tipo"] != "fecho":
        raise RoteiroErro("O roteiro precisa começar com um gancho e terminar com um fecho.")
    palavras = sum(len(c["fala"].split()) for c in cenas)
    if palavras > TOTAL_PALAVRAS + 10:
        raise RoteiroErro(
            f"A narração ficou longa demais para um Reels ({palavras} palavras; até "
            f"{TOTAL_PALAVRAS}). Corte {palavras - TOTAL_PALAVRAS} palavras ou mais: frases mais "
            "curtas e, se precisar, uma cena a menos."
        )
    titulo = _texto(dados.get("titulo"), 60) or _texto(cenas[0].get("texto"), 60)
    return Roteiro(titulo, str(dados.get("legenda") or "").strip()[:LIMITE_LEGENDA], cenas)
