"""O dia em dados, para a abertura: uma lista de blocos, cada um com o que o painel mostra e o
que o Zé fala. Os blocos seguem o menu do Zé, agrupados em cenas: `agora` (a hora e o clima),
`hoje` (a agenda, as automações e o Foco), `redes` (o WhatsApp e o Instagram, as Redes sociais),
`atividade` (o que o Zé fez e as sessões trabalhando), `pendencias` (o que pede quem usa, com a
seção do menu de cada item) e `noticias` (as manchetes, numa faixa). Bloco sem nada não entra.
O último, `fim`, é só a fala de fechamento.

Tudo aqui é puro: quem chama junta as fontes (`servico.coletar`) e passa o momento.
"""

import re
from collections.abc import Sequence
from datetime import datetime
from typing import Any, NamedTuple

from zervis.abertura.clima import Clima
from zervis.abertura.noticias import Noticia
from zervis.redes.analise import curto

DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado",
        "domingo")  # fmt: skip
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro")  # fmt: skip
NUMEROS = ("zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez")
FALADOS = 3  # quantos itens de cada bloco o Zé fala (o painel mostra mais)
MANCHETES_FALADAS = 2
MOSTRADOS = 5
PENDENCIAS_MOSTRADAS = 6
CHUVA_PROVAVEL = 50  # % de chance numa hora para ela contar como hora de chuva
FECHAMENTO = "Esse é o seu dia. Quando quiser, é só chamar."
# O começo de cada fala da abertura: reconhece uma que tenha ido parar na fila de avisos.
JEITO_DE_FALA = re.compile(
    r"(Bom dia|Boa tarde|Boa noite)(, [^.]+)?\. Hoje é |Esse é o seu dia\.|No WhatsApp, \S+ "
    r"conversas? espera|Em [^,]+, faz -?\d+ graus|No foco, |No Instagram, você tem |"
    r"Nas manchetes de hoje: |Hoje você tem \S+ compromisso|\S+ sess(ão|ões) de código pede|"
    r"Hoje rodam? \S+ automaç|Nos últimos \S+ dias, atendi |\S+ ite(m|ns) pedem? você|"
    r"\S+ sess(ão|ões) de código est(á|ão) trabalhando|Hoje \S+ automaç(ão|ões) rod"
)


class Item(NamedTuple):
    """Um compromisso da agenda ou uma automação de hoje."""

    quando: datetime
    titulo: str
    tipo: str  # "compromisso" ou "automacao"


class SessaoParada(NamedTuple):
    nome: str
    situacao: str  # "interrompida", "limite", "erro" ou "trabalhando"


class Conversa(NamedTuple):
    nome: str
    quando: float  # a última mensagem dele (epoch)


class Publicacao(NamedTuple):
    quando: float  # epoch
    visualizacoes: float
    legenda: str


class Instagram(NamedTuple):
    """O perfil de quem usa e as publicações mais novas (a mais nova primeiro)."""

    usuario: str
    seguidores: int
    publicacoes: Sequence[Publicacao]


class Foco(NamedTuple):
    """As frentes de quem usa (zervis/foco): a atual e quantas há em cada estado."""

    atual: str  # o título da frente atual ("" sem frente ativa)
    proximo_passo: str
    ativas: int
    travadas: int
    pausadas: int
    feitas_semana: int


class Atividade(NamedTuple):
    """O que o Zé fez nos últimos dias (zervis/atividade.py) e as automações que rodaram hoje."""

    pedidos: int
    acoes: int
    falhas: int
    por_dia: Sequence[tuple[str, int, int]] = ()  # (dia ISO, registros, falhas); o último é hoje
    automacoes: int = 0  # as que rodaram hoje
    dias: int = 7


class Pendencia(NamedTuple):
    """Algo que espera quem usa, com a seção do menu onde se resolve."""

    area: str  # "Sessões", "Automações", "Autodesenvolvimento", "Memória", "Atualizações"
    titulo: str
    detalhe: str
    nivel: str  # "critico", "alerta" ou "info"
    fala: str  # o pedaço da frase do Zé ("a sessão Loja parou no meio")


SEMANA_S = 7 * 86400
NO_GRAFICO = 6  # publicações no gráfico do painel
LEGENDA = 60


SITUACOES = {
    "interrompida": ("Interrompida", "parou no meio"),
    "limite": ("Limite da conta", "bateu no limite da conta"),
    "erro": ("Erro", "parou com erro"),
    "trabalhando": ("Trabalhando", "está trabalhando"),
}


def saudacao(agora: datetime) -> str:
    if 5 <= agora.hour < 12:
        return "Bom dia"
    if 12 <= agora.hour < 18:
        return "Boa tarde"
    return "Boa noite"


def data_por_extenso(agora: datetime) -> str:
    return f"{DIAS[agora.weekday()]}, {agora.day} de {MESES[agora.month - 1]}"


def quantos(n: int, singular: str, plural: str, feminino: bool = False) -> str:
    """`quantos(2, "conversa", "conversas", True)` -> "duas conversas" (a voz lê melhor)."""
    if feminino and n in (1, 2):
        palavra = ("uma", "duas")[n - 1]
    else:
        palavra = NUMEROS[n] if n < len(NUMEROS) else str(n)
    return f"{palavra} {singular if n == 1 else plural}"


def hora_falada(quando: datetime) -> str:
    horas = "1 hora" if quando.hour == 1 else f"{quando.hour} horas"
    return f"{horas} e {quando.minute}" if quando.minute else horas


def enumerar(partes: Sequence[str]) -> str:
    """ "a", "b" e "c"."""
    if len(partes) <= 1:
        return "".join(partes)
    return f"{', '.join(partes[:-1])} e {partes[-1]}"


def _ha(agora: float, quando: float) -> str:
    minutos = max(0, round((agora - quando) / 60))
    if minutos < 60:
        return f"há {minutos} min" if minutos else "agora"
    return f"há {round(minutos / 60)} h"


def _maiuscula(frase: str) -> str:
    return frase[:1].upper() + frase[1:]


def _hora_de_chuva(c: Clima | None, hora: int) -> bool:
    return c is not None and hora < len(c.chuva_horas) and c.chuva_horas[hora] >= CHUVA_PROVAVEL


def _fala_do_clima(c: Clima, agora: datetime) -> str:
    fala = f"Em {c.cidade}, faz {c.temperatura} graus"
    fala += f", com {c.ceu}." if c.ceu else "."
    fala += f" Máxima de {c.maxima} e mínima de {c.minima}"
    if c.chuva < 20:
        return fala + "."
    fala += f", com {c.chuva} por cento de chance de chuva"
    # a primeira hora de chuva que ainda vem (se já chove agora, não precisa dizer)
    if not _hora_de_chuva(c, agora.hour):
        vem = next((h for h in range(agora.hour + 1, 24) if _hora_de_chuva(c, h)), None)
        if vem is not None:
            fala += f", a partir das {vem} horas"
    return fala + "."


def _agora(agora: datetime, nome: str, c: Clima | None) -> dict[str, Any]:
    """A hora, a saudação e o clima: a primeira cena."""
    oi = f"{saudacao(agora)}, {nome}" if nome else saudacao(agora)
    data = data_por_extenso(agora)
    fala = f"{oi}. Hoje é {data}."
    if c is not None:
        fala += " " + _fala_do_clima(c, agora)
    return {
        "tipo": "agora",
        "saudacao": oi,
        "data": data,
        "clima": c._asdict() if c is not None else None,
        "fala": fala,
    }


def _fala_do_foco(f: Foco) -> str:
    if f.atual:
        fala = f"No foco, você estava em {f.atual.rstrip('.')}"
        fala += f"; o próximo passo é {f.proximo_passo.rstrip('.')}." if f.proximo_passo else "."
    else:
        fala = "No foco, nenhuma frente ativa agora."
    if f.travadas:
        travadas = quantos(f.travadas, "frente está travada", "frentes estão travadas", True)
        fala += f" {_maiuscula(travadas)}."
    return fala  # as feitas na semana ficam só no painel: a fala é curta


def _hoje(itens: Sequence[Item], foco: Foco | None, c: Clima | None) -> dict[str, Any]:
    """A agenda, as automações de hoje e o Foco: o dia de quem usa."""
    itens = sorted(itens, key=lambda i: i.quando)
    compromissos = [i for i in itens if i.tipo == "compromisso"]
    automacoes = [i for i in itens if i.tipo == "automacao"]
    frases = []
    if compromissos:
        partes = [f"às {hora_falada(i.quando)}, {i.titulo}" for i in compromissos[:FALADOS]]
        frases.append(
            f"Hoje você tem {quantos(len(compromissos), 'compromisso', 'compromissos')}: "
            f"{enumerar(partes)}."
        )
        # o clima cruzado com a agenda: o primeiro compromisso numa hora de chuva
        molhado = next((i for i in compromissos if _hora_de_chuva(c, i.quando.hour)), None)
        if molhado is not None:
            frases.append(f"Há chuva prevista para a hora de {molhado.titulo.rstrip('.')}.")
    if automacoes:
        partes = [f"{i.titulo}, às {hora_falada(i.quando)}" for i in automacoes[:FALADOS]]
        comeco = "E" if compromissos else "Hoje"
        frases.append(
            f"{comeco} {'roda' if len(automacoes) == 1 else 'rodam'} "
            f"{quantos(len(automacoes), 'automação', 'automações', True)}: {enumerar(partes)}."
        )
    if foco is not None:
        frases.append(_fala_do_foco(foco))
    return {
        "tipo": "hoje",
        "itens": [
            {
                "hora": i.quando.strftime("%H:%M"),
                "titulo": i.titulo,
                "tipo": i.tipo,
                "chuva": i.tipo == "compromisso" and _hora_de_chuva(c, i.quando.hour),
            }
            for i in itens[:MOSTRADOS]
        ],
        "total": len(itens),
        "foco": foco._asdict() if foco is not None else None,
        "fala": " ".join(frases),
    }


def _fala_do_whatsapp(conversas: Sequence[Conversa]) -> str:
    total = quantos(len(conversas), "conversa", "conversas", True)
    verbo = "espera" if len(conversas) == 1 else "esperam"
    # só nomes: um número de telefone lido dígito por dígito não diz nada (visto em 11/11/2026)
    nomes = [c.nome for c in conversas if not c.nome.lstrip("+").replace(" ", "").isdigit()]
    falados = nomes[:FALADOS]
    resto = len(conversas) - len(falados)
    if not falados:
        return f"No WhatsApp, {total} {verbo} resposta."
    if resto in (1, 2):
        falados.append(f"mais {('uma', 'duas')[resto - 1]}")
    elif resto:
        falados.append(f"mais {NUMEROS[resto] if resto < len(NUMEROS) else resto}")
    return f"No WhatsApp, {total} {verbo} resposta: {enumerar(falados)}."


def _whatsapp(conversas: Sequence[Conversa], agora: float) -> dict[str, Any]:
    return {
        "itens": [
            {
                "nome": c.nome,
                "ha": _ha(agora, c.quando),
                "min": max(0, round((agora - c.quando) / 60)),
            }
            for c in conversas[:MOSTRADOS]
        ],
        "total": len(conversas),
    }


def _instagram(ig: Instagram, agora: datetime) -> tuple[dict[str, Any], str]:
    semana = [p for p in ig.publicacoes if agora.timestamp() - p.quando <= SEMANA_S]
    fala = f"No Instagram, você tem {curto(ig.seguidores)} seguidores."
    if semana:
        melhor = max(semana, key=lambda p: p.visualizacoes)
        saiu = "saiu" if len(semana) == 1 else "saíram"
        fala += (
            f" Nesta semana {saiu} {quantos(len(semana), 'publicação', 'publicações', True)}; "
            f"a que mais rendeu teve {curto(melhor.visualizacoes)} visualizações."
        )
    else:
        fala += " Nesta semana não saiu publicação nova."
    grafico = list(reversed(ig.publicacoes[:NO_GRAFICO]))  # a mais antiga à esquerda
    destaque = max(semana or ig.publicacoes, key=lambda p: p.visualizacoes, default=None)
    return {
        "usuario": ig.usuario,
        "seguidores": ig.seguidores,
        "semana": len(semana),
        "grafico": [
            {
                "rotulo": datetime.fromtimestamp(p.quando, agora.tzinfo).strftime("%d/%m"),
                "valor": round(p.visualizacoes),
            }
            for p in grafico
        ],
        "destaque": (
            {"legenda": destaque.legenda[:LEGENDA], "valor": curto(destaque.visualizacoes)}
            if destaque
            else None
        ),
    }, fala


def _redes(conversas: Sequence[Conversa], ig: Instagram | None, agora: datetime) -> dict[str, Any]:
    """As Redes sociais do menu: o WhatsApp sem resposta e o Instagram, numa cena só."""
    conversas = sorted(conversas, key=lambda c: -c.quando)
    falas = []
    whatsapp = instagram = None
    if conversas:
        whatsapp = _whatsapp(conversas, agora.timestamp())
        falas.append(_fala_do_whatsapp(conversas))
    if ig is not None:
        instagram, fala = _instagram(ig, agora)
        falas.append(fala)
    return {"tipo": "redes", "whatsapp": whatsapp, "instagram": instagram, "fala": " ".join(falas)}


def _atividade(a: Atividade | None, trabalhando: Sequence[str]) -> dict[str, Any]:
    """A Atividade do menu: o que o Zé fez nos últimos dias, as automações que rodaram hoje e as
    sessões de código trabalhando agora."""
    a = a or Atividade(0, 0, 0)
    frases = []
    if a.pedidos or a.acoes:
        fala = (
            f"Nos últimos {NUMEROS[a.dias] if a.dias < len(NUMEROS) else a.dias} dias, atendi "
            f"{quantos(a.pedidos, 'pedido', 'pedidos')} e executei "
            f"{quantos(a.acoes, 'ação', 'ações', True)}"
        )
        fala += f", com {quantos(a.falhas, 'falha', 'falhas', True)}." if a.falhas else "."
        frases.append(fala)
    if a.automacoes:
        rodou = "rodou" if a.automacoes == 1 else "rodaram"
        frases.append(f"Hoje {quantos(a.automacoes, 'automação', 'automações', True)} {rodou}.")
    if trabalhando:
        sujeito = quantos(
            len(trabalhando), "sessão de código está", "sessões de código estão", True
        )
        frases.append(f"{_maiuscula(sujeito)} trabalhando: {enumerar(trabalhando[:FALADOS])}.")
    return {
        "tipo": "atividade",
        "dias": a.dias,
        "pedidos": a.pedidos,
        "acoes": a.acoes,
        "falhas": a.falhas,
        "por_dia": [{"dia": d, "registros": n, "falhas": f} for d, n, f in a.por_dia],
        "automacoes": a.automacoes,
        "sessoes": list(trabalhando[:MOSTRADOS]),
        "fala": " ".join(frases),
    }


def pendencias(
    sessoes: Sequence[SessaoParada] = (),
    automacoes_com_erro: Sequence[str] = (),
    melhorias: int = 0,
    sugestoes: int = 0,
    atualizacao: bool = False,
) -> list[Pendencia]:
    """O que espera quem usa, do mais grave para o menos, cada item com a seção do menu."""
    lista = [
        Pendencia(
            "Sessões",
            s.nome,
            SITUACOES[s.situacao][0],
            "critico" if s.situacao == "erro" else "alerta",
            f"a sessão {s.nome} {SITUACOES[s.situacao][1]}",
        )
        for s in sessoes
        if s.situacao != "trabalhando"
    ]
    lista += [
        Pendencia("Automações", nome, "Falhou", "critico", f"a automação {nome} falhou")
        for nome in automacoes_com_erro
    ]
    if melhorias:
        prontas = quantos(melhorias, "melhoria pronta", "melhorias prontas", True)
        lista.append(
            Pendencia(
                "Autodesenvolvimento",
                "Melhorias prontas",
                f"{melhorias} para aprovar",
                "info",
                f"há {prontas} para aprovar",
            )
        )
    if sugestoes:
        esperam = quantos(
            sugestoes, "sugestão de memória espera", "sugestões de memória esperam", True
        )
        lista.append(
            Pendencia(
                "Memória", "Sugestões", f"{sugestoes} para decidir", "info", f"{esperam} decisão"
            )
        )
    if atualizacao:
        lista.append(
            Pendencia(
                "Atualizações", "Nova versão", "Disponível", "info", "há uma atualização disponível"
            )
        )
    ordem = ("critico", "alerta", "info")
    return sorted(lista, key=lambda x: ordem.index(x.nivel))


def _pendencias(lista: Sequence[Pendencia]) -> dict[str, Any]:
    falados = [x.fala for x in lista[:FALADOS]]
    if (resto := len(lista) - len(falados)) > 0:
        falados.append(f"mais {quantos(resto, 'item', 'itens')}")
    pedem = quantos(len(lista), "item pede", "itens pedem")
    areas: dict[str, int] = {}
    for x in lista:
        areas[x.area] = areas.get(x.area, 0) + 1
    return {
        "tipo": "pendencias",
        "itens": [
            {"area": x.area, "titulo": x.titulo, "detalhe": x.detalhe, "nivel": x.nivel}
            for x in lista[:PENDENCIAS_MOSTRADAS]
        ],
        "total": len(lista),
        "areas": [{"area": area, "n": n} for area, n in areas.items()],
        "fala": f"{_maiuscula(pedem)} você: {enumerar(falados)}.",
    }


def _noticias(noticias: Sequence[Noticia]) -> dict[str, Any]:
    falas = " ".join(f"{n.titulo.rstrip('.')}." for n in noticias[:MANCHETES_FALADAS])
    return {
        "tipo": "noticias",
        "itens": [n._asdict() for n in noticias[:MOSTRADOS]],
        "fala": f"Nas manchetes de hoje: {falas}",
    }


def montar(
    agora: datetime,
    nome: str = "",
    clima: Clima | None = None,
    hoje: Sequence[Item] = (),
    sessoes: Sequence[SessaoParada] = (),
    conversas: Sequence[Conversa] = (),
    noticias: Sequence[Noticia] = (),
    instagram: Instagram | None = None,
    foco: Foco | None = None,
    atividade: Atividade | None = None,
    pedem: Sequence[Pendencia] = (),
) -> dict[str, Any]:
    """`sessoes`: as que trabalham vão para a Atividade; as paradas, para as Pendências, junto
    com `pedem` (o que mais espera quem usa: `pendencias()`)."""
    if foco is not None and not (foco.atual or foco.ativas or foco.travadas or foco.pausadas):
        foco = None
    blocos = [_agora(agora, nome, clima)]
    if hoje or foco is not None:
        blocos.append(_hoje(hoje, foco, clima))
    if conversas or instagram is not None:
        blocos.append(_redes(conversas, instagram, agora))
    trabalhando = [s.nome for s in sessoes if s.situacao == "trabalhando"]
    fez = atividade is not None and (
        atividade.pedidos or atividade.acoes or atividade.falhas or atividade.automacoes
    )
    if fez or trabalhando:
        blocos.append(_atividade(atividade, trabalhando))
    ordem = ("critico", "alerta", "info")
    todas = sorted([*pendencias(sessoes), *pedem], key=lambda x: ordem.index(x.nivel))
    if todas:
        blocos.append(_pendencias(todas))
    if noticias:
        blocos.append(_noticias(noticias))
    blocos.append({"tipo": "fim", "fala": FECHAMENTO})
    return {"montado": agora.isoformat(timespec="seconds"), "blocos": blocos}
