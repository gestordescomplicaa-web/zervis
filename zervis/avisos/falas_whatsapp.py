"""As leituras do WhatsApp que o Zé fala sozinho, sem o cérebro e sem gastar token (ADR 0056):
"quem me mandou mensagem?", "tem alguém esperando?", "quem está na lista?" e "lê a mensagem da
Ana". Saem do arquivo do WhatsApp, em frases curtas para ouvir.
"""

from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from zervis.avisos.caixa import Caixa, Conversa, descrever
from zervis.avisos.modo import para_ouvir
from zervis.avisos.pendentes import lista_falada
from zervis.avisos.prioridade import Prioridade


def _nunca(chat: str, telefone: str) -> bool:
    return False


LIDAS = 3  # mensagens lidas de uma conversa; mais que isso, o cérebro (whatsapp_ler)
TRECHO = 160  # caracteres de cada mensagem lida


def quando(momento: float, agora: float, fuso: ZoneInfo) -> str:
    """ "às 10:42", "ontem às 18:05" ou "no dia 28/10 às 09:10"."""
    hora = datetime.fromtimestamp(momento, fuso)
    hoje = datetime.fromtimestamp(agora, fuso).date()
    if hora.date() == hoje:
        return f"às {hora:%H:%M}"
    if (hoje - hora.date()).days == 1:
        return f"ontem às {hora:%H:%M}"
    return f"no dia {hora:%d/%m} às {hora:%H:%M}"


def _trecho(m: dict[str, object]) -> str:
    return para_ouvir(descrever(m), limite=TRECHO) or "uma mensagem sem texto"


def _esperando(c: Conversa, calado: Callable[[str, str], bool]) -> bool:
    return c.sem_resposta and not calado(c.chat, c.telefone)


def quem(caixa: Caixa, fuso: ZoneInfo, calado: Callable[[str, str], bool] = _nunca) -> str:
    recebidas = caixa.recebidas(5)
    if not recebidas:
        return "Nenhuma mensagem no WhatsApp ainda."
    c = recebidas[0]
    m = c.mensagens[0]
    frase = f"A última foi de {c.nome}, {quando(float(m['quando']), caixa.agora(), fuso)}: "
    frase += _trecho(m)
    if not c.sem_resposta:
        frase += " Você já respondeu."
    outros = [x.nome for x in recebidas[1:] if _esperando(x, calado)]
    if outros:
        frase += f" Também esperam resposta: {lista_falada(outros)}."
    return frase


def esperando(caixa: Caixa, fuso: ZoneInfo, calado: Callable[[str, str], bool] = _nunca) -> str:
    aguardam = [c for c in caixa.recebidas(20) if _esperando(c, calado)]
    if not aguardam:
        return "Ninguém esperando a sua resposta no WhatsApp."
    agora = caixa.agora()
    itens = [f"{c.nome}, {quando(c.mensagens[0]['quando'], agora, fuso)}" for c in aguardam[:5]]
    mais = f" e mais {len(aguardam) - 5}" if len(aguardam) > 5 else ""
    total = "Uma pessoa espera" if len(aguardam) == 1 else f"{len(aguardam)} pessoas esperam"
    return f"{total} a sua resposta: {'; '.join(itens)}{mais}."


def lista(prioridade: Prioridade) -> str:
    todos = prioridade.todos()
    if not todos:
        return "A lista de prioridade está vazia."
    de_vez = [v.nome for v in todos if v.motivo == "pedido"]
    resposta = [v.nome for v in todos if v.motivo == "resposta"]
    calados = [v.nome for v in todos if v.motivo == "silencio"]
    partes = []
    if de_vez:
        partes.append(f"Na lista de prioridade: {lista_falada(de_vez)}.")
    if resposta:
        partes.append(f"Esperando a resposta ao que mandei por você: {lista_falada(resposta)}.")
    if calados:
        partes.append(f"Silenciados: {lista_falada(calados)}.")
    return " ".join(partes)


def ler(caixa: Caixa, nome: str, fuso: ZoneInfo) -> str:
    c: Conversa | None = caixa.achar(nome)
    if c is None:
        return f"Não achei uma conversa só com {nome} no WhatsApp."
    dele = [m for m in caixa.mensagens(c.chat, 12) if not m.get("de_mim")][-LIDAS:]
    if not dele:
        return f"{c.nome} ainda não mandou mensagem."
    agora = caixa.agora()
    lidas = [f"{quando(float(m['quando']), agora, fuso)}: {_trecho(m)}" for m in dele]
    inicio = "No grupo" if c.grupo else "De"
    return f"{inicio} {c.nome}, " + " ".join(lidas)
