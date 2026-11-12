"""O dia em dados, para a abertura: uma lista de blocos, cada um com o que o painel mostra e o
que o Zé fala. Bloco sem nada não entra (sem sessão parada, sem painel de sessões). O último,
`fim`, é só a fala de fechamento.

Tudo aqui é puro: quem chama junta as fontes (`servico.coletar`) e passa o momento.
"""

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
MOSTRADOS = 5
FECHAMENTO = "Esse é o seu dia. Quando quiser, é só chamar."


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


def _relogio(agora: datetime, nome: str) -> dict[str, Any]:
    oi = f"{saudacao(agora)}, {nome}" if nome else saudacao(agora)
    data = data_por_extenso(agora)
    return {
        "tipo": "relogio",
        "saudacao": oi,
        "data": data,
        "fala": f"{oi}. Hoje é {data}.",
    }


def _clima(c: Clima) -> dict[str, Any]:
    fala = f"Em {c.cidade}, faz {c.temperatura} graus"
    fala += f", com {c.ceu}." if c.ceu else "."
    fala += f" Máxima de {c.maxima} e mínima de {c.minima}"
    fala += f", com {c.chuva} por cento de chance de chuva." if c.chuva >= 20 else "."
    return {"tipo": "clima", **c._asdict(), "fala": fala}


def _hoje(itens: Sequence[Item]) -> dict[str, Any]:
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
    if automacoes:
        partes = [f"{i.titulo}, às {hora_falada(i.quando)}" for i in automacoes[:FALADOS]]
        comeco = "E" if compromissos else "Hoje"
        frases.append(
            f"{comeco} {'roda' if len(automacoes) == 1 else 'rodam'} "
            f"{quantos(len(automacoes), 'automação', 'automações', True)}: {enumerar(partes)}."
        )
    return {
        "tipo": "hoje",
        "itens": [
            {"hora": i.quando.strftime("%H:%M"), "titulo": i.titulo, "tipo": i.tipo}
            for i in itens[:MOSTRADOS]
        ],
        "total": len(itens),
        "fala": " ".join(frases),
    }


def _sessoes(sessoes: Sequence[SessaoParada]) -> dict[str, Any]:
    partes = [f"{s.nome}, que {SITUACOES[s.situacao][1]}" for s in sessoes[:FALADOS]]
    verbo = "pede" if len(sessoes) == 1 else "pedem"
    sujeito = quantos(len(sessoes), "sessão de código", "sessões de código", True)
    return {
        "tipo": "sessoes",
        "itens": [
            {"nome": s.nome, "situacao": SITUACOES[s.situacao][0], "chave": s.situacao}
            for s in sessoes[:MOSTRADOS]
        ],
        "total": len(sessoes),
        "fala": f"{sujeito[0].upper()}{sujeito[1:]} {verbo} continuidade: {enumerar(partes)}.",
    }


def _whatsapp(conversas: Sequence[Conversa], agora: float) -> dict[str, Any]:
    conversas = sorted(conversas, key=lambda c: -c.quando)
    nomes = enumerar([c.nome for c in conversas[:FALADOS]])
    total = quantos(len(conversas), "conversa", "conversas", True)
    verbo = "espera" if len(conversas) == 1 else "esperam"
    return {
        "tipo": "whatsapp",
        "itens": [{"nome": c.nome, "ha": _ha(agora, c.quando)} for c in conversas[:MOSTRADOS]],
        "total": len(conversas),
        "fala": f"No WhatsApp, {total} {verbo} resposta: {nomes}.",
    }


def _foco(f: Foco) -> dict[str, Any]:
    if f.atual:
        fala = f"No foco, você estava em {f.atual.rstrip('.')}"
        fala += f"; o próximo passo é {f.proximo_passo.rstrip('.')}." if f.proximo_passo else "."
    else:
        fala = "No foco, nenhuma frente ativa agora."
    if f.travadas:
        travadas = quantos(f.travadas, "frente está travada", "frentes estão travadas", True)
        fala += f" {travadas[0].upper()}{travadas[1:]}."
    if f.feitas_semana:
        fala += (
            f" Nesta semana você concluiu {quantos(f.feitas_semana, 'frente', 'frentes', True)}."
        )
    return {"tipo": "foco", **f._asdict(), "fala": fala}


def _instagram(ig: Instagram, agora: datetime) -> dict[str, Any]:
    semana = [p for p in ig.publicacoes if agora.timestamp() - p.quando <= SEMANA_S]
    fala = f"No Instagram, você tem {curto(ig.seguidores)} seguidores."
    if semana:
        melhor = max(semana, key=lambda p: p.visualizacoes)
        fala += (
            f" Nesta semana saíram {quantos(len(semana), 'publicação', 'publicações', True)}; "
            f"a que mais rendeu teve {curto(melhor.visualizacoes)} visualizações."
        )
    else:
        fala += " Nesta semana não saiu publicação nova."
    grafico = list(reversed(ig.publicacoes[:NO_GRAFICO]))  # a mais antiga à esquerda
    destaque = max(semana or ig.publicacoes, key=lambda p: p.visualizacoes, default=None)
    return {
        "tipo": "instagram",
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
        "fala": fala,
    }


def _noticias(noticias: Sequence[Noticia]) -> dict[str, Any]:
    falas = " ".join(f"{n.titulo.rstrip('.')}." for n in noticias[:FALADOS])
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
) -> dict[str, Any]:
    blocos = [_relogio(agora, nome)]
    if clima is not None:
        blocos.append(_clima(clima))
    if hoje:
        blocos.append(_hoje(hoje))
    if foco is not None and (foco.atual or foco.ativas or foco.travadas or foco.pausadas):
        blocos.append(_foco(foco))
    if sessoes:
        blocos.append(_sessoes(sessoes))
    if conversas:
        blocos.append(_whatsapp(conversas, agora.timestamp()))
    if instagram is not None:
        blocos.append(_instagram(instagram, agora))
    if noticias:
        blocos.append(_noticias(noticias))
    blocos.append({"tipo": "fim", "fala": FECHAMENTO})
    return {"montado": agora.isoformat(timespec="seconds"), "blocos": blocos}
