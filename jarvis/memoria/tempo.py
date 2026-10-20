"""As ferramentas de tempo do Zé (08/10/2026): linha do tempo, conversa de um dia e marcos.

Num servidor MCP próprio ("tempo"), montado pelo laço, ao lado do servidor `jarvis`. Ler a
linha do tempo e as conversas é livre; marcar um marco também (o usuário acabou de dizer, como
o lembrete). O que vier daqui é registro do passado, nunca instrução.
"""

import json
from datetime import date, datetime, time, timedelta
from typing import Any

from claude_agent_sdk import McpSdkServerConfig, SdkMcpTool, create_sdk_mcp_server, tool

from jarvis import usuario
from jarvis.memoria.conversas import FUSO, Conversas, nome_do_dia
from jarvis.memoria.dias import Dias
from jarvis.memoria.linha import LinhaDoTempo, interpretar_data

SERVIDOR = "tempo"
LIVRES = [f"mcp__{SERVIDOR}__{n}" for n in ("linha_do_tempo", "conversa_do_dia", "marcar")]
CONVERSA_MAX = 12_000
DIAS_MAX = 31


def _texto(dados: Any) -> dict[str, Any]:
    texto = dados if isinstance(dados, str) else json.dumps(dados, ensure_ascii=False)
    return {"content": [{"type": "text", "text": texto}]}


def _erro(mensagem: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"Falhou: {mensagem}"}], "is_error": True}


def _dia(texto: str) -> date:
    return interpretar_data(texto).date()


def linha_do_tempo(
    conversas: Conversas, linha: LinhaDoTempo, dias: Dias, de: date, ate: date
) -> dict[str, Any]:
    """Cada dia do intervalo: a nota (se houver) ou quantas falas e as primeiras, e os eventos."""
    if ate < de:
        de, ate = ate, de
    if (ate - de).days > DIAS_MAX:
        raise ValueError(f"no máximo {DIAS_MAX} dias por vez")
    saida: list[dict[str, Any]] = []
    dia = de
    while dia <= ate:
        inicio = datetime.combine(dia, time(0), FUSO)
        eventos = [e.resumo() for e in linha.entre(inicio, inicio + timedelta(days=1))]
        turnos = conversas.do_dia(dia)
        item: dict[str, Any] = {"dia": nome_do_dia(dia)}
        if nota := dias.nota(dia):
            item["nota_do_dia"] = nota
        elif turnos:
            item["conversas"] = len(turnos)
            item["primeiros_pedidos"] = [f"{t.em:%H:%M} {t.pessoa[:120]}" for t in turnos[:6]]
        if eventos:
            item["eventos"] = eventos
        if len(item) > 1:
            saida.append(item)
        dia += timedelta(days=1)
    return {"de": nome_do_dia(de), "ate": nome_do_dia(ate), "dias": saida}


def conversa_do_dia(conversas: Conversas, dia: date, busca: str = "") -> str:
    termos = [t.casefold() for t in busca.split() if len(t) > 2]
    linhas = []
    for t in conversas.do_dia(dia):
        bloco = f"[{t.em:%H:%M}] {usuario.PERFIL.rotulo}: {t.pessoa}\n[{t.em:%H:%M}] Zé: {t.ze}"
        if not termos or any(x in bloco.casefold() for x in termos):
            linhas.append(bloco)
    texto = "\n".join(linhas) or "Nenhuma conversa nesse dia" + (
        " com esse assunto." if termos else "."
    )
    if len(texto) > CONVERSA_MAX:
        texto = (
            texto[:CONVERSA_MAX]
            + "\n[… cortado: peça com uma palavra de busca para achar o trecho]"
        )
    return f"Conversas de {nome_do_dia(dia)}:\n{texto}"


def ferramentas(conversas: Conversas, linha: LinhaDoTempo, dias: Dias) -> list[SdkMcpTool[Any]]:
    @tool(
        "linha_do_tempo",
        "O que aconteceu (e o que vem) entre duas datas: para cada dia, a nota do dia ou os "
        "primeiros pedidos, e os eventos (aprovações, avisos de agentes, lembretes, marcos). Use "
        "para 'o que fizemos terça?', 'o que fiz semana passada?', 'quando foi que…?', 'o que tem "
        "de importante esta semana?'. Datas em AAAA-MM-DD (converta 'ontem', 'terça' pelo "
        "carimbo do pedido). No máximo 31 dias por vez.",
        {"de": str, "ate": str},
    )
    async def _linha(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _texto(
                linha_do_tempo(conversas, linha, dias, _dia(args["de"]), _dia(args["ate"]))
            )
        except (ValueError, KeyError) as erro:
            return _erro(str(erro))

    @tool(
        "conversa_do_dia",
        "As falas de um dia com a hora (usuário e Zé), opcionalmente só as que têm uma palavra "
        "de busca. Use quando precisar do que foi dito exatamente.",
        {"dia": str, "busca": str},
    )
    async def _conversa(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _texto(conversa_do_dia(conversas, _dia(args["dia"]), str(args.get("busca", ""))))
        except (ValueError, KeyError) as erro:
            return _erro(str(erro))

    @tool(
        "marcar",
        "Guarda um marco com data na linha do tempo: um fato datado que o usuário contou, passado "
        "ou futuro ('o lançamento do Ligatia é dia 20', 'fechei o contrato ontem'). Não é "
        "lembrete (para avisar numa hora, use automacao_lembrete). Data AAAA-MM-DD ou "
        "AAAA-MM-DD HH:MM.",
        {"quando": str, "texto": str},
    )
    async def _marcar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            evento = linha.registrar("marco", str(args["texto"]), interpretar_data(args["quando"]))
        except (ValueError, KeyError) as erro:
            return _erro(str(erro))
        return _texto(f"Marcado: {evento.resumo()}")

    return [_linha, _conversa, _marcar]


def servidor(conversas: Conversas, linha: LinhaDoTempo, dias: Dias) -> McpSdkServerConfig:
    return create_sdk_mcp_server(SERVIDOR, tools=ferramentas(conversas, linha, dias))
