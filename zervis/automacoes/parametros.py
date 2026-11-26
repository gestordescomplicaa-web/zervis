"""O que se muda numa automação (ADR 0141): a agenda dita como gente e os parâmetros de cada tipo.

As Automações mandam em tudo o que roda sozinho: o Marketing não agenda mais nada por conta
própria. O painel e a voz leem e mudam pelos mesmos caminhos daqui:

- a **agenda** vira frase ("Segunda, quarta e sexta, 9h") e, para o formulário, as partes dela
  (os dias e a hora, uma data, um intervalo); o formulário volta a ser um dos formatos de
  `agenda.interpretar`;
- os **parâmetros** de cada tipo: o texto do lembrete e da pergunta; o tema do artigo; os temas e a
  duração do vídeo; os temas do carrossel; e o "publicar sozinho" dos três de marketing (ADR 0126).
  A ligação não muda por aqui: o número e o recado foram aprovados pela voz quando ela foi
  agendada.
"""

import json
import re
from typing import Any

from zervis.automacoes.agenda import AgendaInvalida, _campo, interpretar

NOMES = {
    "lembrete": "Lembrete",
    "pergunta": "Pergunta ao Zé",
    "ligacao": "Ligação",
    "artigo": "Artigo do blog",
    "video": "Vídeo",
    "post": "Carrossel",
}
DIAS = ("Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado")  # cron: 0 = domingo
MARKETING = ("artigo", "video", "post")
_SEMANAL = re.compile(r"cron (\d{1,2}) (\d{1,2}) \* \* (\S+)")
_INTERVALO = re.compile(r"a cada (\d+)(d|h|m)")
UNIDADES = {"m": ("minuto", "minutos"), "h": ("hora", "horas"), "d": ("dia", "dias")}
_UMA = {"m": "A cada minuto", "h": "A cada hora", "d": "Todo dia"}


class ParametroErro(ValueError):
    """Mensagem curta, pronta para a tela."""


# --- a agenda ------------------------------------------------------------------------------------


def _hora(h: int, m: int) -> str:
    return f"{h}h{m:02d}" if m else f"{h}h"


def _dias(dias: list[int]) -> str:
    if dias == [1, 2, 3, 4, 5]:
        return "Dias úteis"
    if len(dias) == 7:
        return "Todo dia"
    if len(dias) == 1:
        return (
            f"Toda {DIAS[dias[0]].lower()}"
            if dias[0] not in (0, 6)
            else f"Todo {DIAS[dias[0]].lower()}"
        )
    nomes = [DIAS[d] if i == 0 else DIAS[d].lower() for i, d in enumerate(dias)]
    return f"{', '.join(nomes[:-1])} e {nomes[-1]}"


def partes(agenda: str) -> dict[str, Any]:
    """A agenda em partes, para o formulário: `semana` (dias de 0 a 6 e a hora), `uma_vez` (a data
    está na próxima vez), `intervalo` (quantos e a unidade) ou `outra` (um cron que o
    formulário não monta; a frase diz qual)."""
    t = " ".join(agenda.lower().split())
    if achado := _SEMANAL.fullmatch(t):
        minuto, hora, semana = int(achado[1]), int(achado[2]), achado[3]
        try:
            dias = sorted(_campo(semana, 0, 6))
        except (AgendaInvalida, ValueError):
            return {"modo": "outra"}
        if minuto <= 59 and hora <= 23:
            return {"modo": "semana", "dias": dias, "hora": f"{hora:02d}:{minuto:02d}"}
    if achado := _INTERVALO.fullmatch(t):
        return {"modo": "intervalo", "quantos": int(achado[1]), "unidade": achado[2]}
    if t.startswith(("cron ", "a cada ")):
        return {"modo": "outra"}
    return {"modo": "uma_vez"}


def frase(agenda: str) -> str:
    """A agenda como gente diz: "cron 0 9 * * 1,3,5" vira "Segunda, quarta e sexta, 9h"."""
    p = partes(agenda)
    if p["modo"] == "semana":
        h, m = (int(x) for x in p["hora"].split(":"))
        return f"{_dias(p['dias'])}, {_hora(h, m)}"
    if p["modo"] == "intervalo":
        if p["quantos"] == 1:
            return _UMA[p["unidade"]]
        return f"A cada {p['quantos']} {UNIDADES[p['unidade']][1]}"
    if p["modo"] == "outra":
        return "Agenda personalizada"
    return "Uma vez"


def montar_agenda(quando: dict[str, Any]) -> str:
    """O formulário de volta a um formato de `agenda.interpretar`; inválido: ParametroErro."""
    modo = str(quando.get("modo") or "")
    if modo == "semana":
        try:
            dias = sorted({int(d) for d in quando.get("dias") or []})
            h, m = (int(x) for x in str(quando.get("hora") or "").split(":"))
        except (TypeError, ValueError):
            raise ParametroErro("Escolha os dias e a hora.") from None
        if not dias or not all(0 <= d <= 6 for d in dias) or not (0 <= h <= 23 and 0 <= m <= 59):
            raise ParametroErro("Escolha os dias e a hora.")
        texto = f"cron {m} {h} * * {','.join(str(d) for d in dias)}"
    elif modo == "uma_vez":
        data, hora = str(quando.get("data") or ""), str(quando.get("hora") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data) or not re.fullmatch(r"\d{2}:\d{2}", hora):
            raise ParametroErro("Escolha a data e a hora.")
        texto = f"{data} {hora}"
    elif modo == "intervalo":
        try:
            quantos = int(quando.get("quantos") or 0)
        except (TypeError, ValueError):
            quantos = 0
        unidade = str(quando.get("unidade") or "")
        if quantos < 1 or unidade not in UNIDADES:
            raise ParametroErro("Intervalo inválido.")
        texto = f"a cada {quantos}{unidade}"
    else:
        raise ParametroErro("Escolha quando.")
    try:
        interpretar(texto)
    except AgendaInvalida as erro:
        raise ParametroErro(str(erro).capitalize() + ".") from None
    return texto


# --- os parâmetros de cada tipo ------------------------------------------------------------------


def _pedido(texto: str) -> dict[str, Any]:
    try:
        dados = json.loads(texto)
    except ValueError:
        return {}
    return dados if isinstance(dados, dict) else {}


def ler(tipo: str, texto: str) -> dict[str, Any]:
    """O que se muda em cada tipo (vazio: só o nome e a agenda)."""
    if tipo in ("lembrete", "pergunta"):
        return {"texto": texto}
    pedido = _pedido(texto)
    publicar = pedido.get("publicar") is True
    temas = [str(t) for t in pedido.get("temas") or [] if str(t).strip()]
    if tipo == "artigo":
        return {"tema": str(pedido.get("tema") or ""), "publicar": publicar}
    if tipo == "video":
        from zervis.video import roteiro

        duracao = int(pedido.get("duracao") or roteiro.DURACAO_PADRAO)
        return {"temas": temas, "duracao": duracao, "publicar": publicar}
    if tipo == "post":
        return {"temas": temas, "publicar": publicar}
    return {}


def montar(tipo: str, texto: str, mudancas: dict[str, Any]) -> str:
    """O texto novo da automação, com as mudanças por cima do que ela tem. Só os campos do tipo
    contam; os outros são ignorados. Inválido: ParametroErro."""
    atuais = ler(tipo, texto)
    if not atuais:
        raise ParametroErro("Esta automação muda só o nome e quando.")
    novos = {**atuais, **{k: v for k, v in mudancas.items() if k in atuais and v is not None}}
    temas = novos.get("temas", [])
    if isinstance(temas, str):
        temas = temas.splitlines()
    publicar = novos.get("publicar") is True
    if tipo in ("lembrete", "pergunta"):
        return str(novos["texto"])
    if tipo == "artigo":
        tema = " ".join(str(novos["tema"]).split())[:120]
        return json.dumps({"tema": tema, "publicar": publicar}, ensure_ascii=False)
    if tipo == "video":
        from zervis.video.videos import VideoErro, Videos

        try:
            return Videos.pedido_agendado(list(temas), int(novos["duracao"]), publicar)
        except (VideoErro, TypeError, ValueError) as erro:
            raise ParametroErro(str(erro) or "Duração inválida.") from None
    from zervis.marketing_posts import PostErro, Posts

    try:
        return Posts.pedido_agendado(list(temas), publicar)
    except PostErro as erro:
        raise ParametroErro(str(erro)) from None
