"""As páginas do painel que não tinham voz (ADR 0128): Empresas, o funil do Instagram em Redes
sociais e a Atividade, onde cai todo acontecimento do Zé. Só leem, então passam sem perguntar;
o funil e a Atividade trazem texto de terceiros e contam como "de fora"."""

import asyncio
from datetime import datetime, timedelta
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis import atividade, empresas, fuso
from zervis.cerebro.ferramentas.comum import _texto

TIPOS = {
    "execucao": "feito",
    "falha": "falha",
    "negada": "negado",
    "pedido": "pedido",
    "nao_entendi": "não entendido",
    "correcao": "correção",
}


def _hora(quando: Any) -> str:
    if not quando:
        return ""
    return datetime.fromtimestamp(float(quando), fuso.local()).strftime("%d/%m %H:%M")


def _curto(bruto: Any, limite: int) -> str:
    texto = " ".join(str(bruto or "").split())
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def ler_empresas() -> dict[str, Any]:
    cadastro = empresas.PADRAO
    lista = []
    for e in cadastro.listar():
        tela = e.para_tela(cadastro.vitrine(e.id))
        lista.append({
            "empresa": e.nome,
            "grupo_do_whatsapp": e.grupo_nome or ("ligado" if e.grupo else "nenhum"),
            "ze_responde_no_grupo": "sim" if e.ligada and e.grupo else "não",
            "projeto": e.pasta,
            "arquivos_na_vitrine": tela.get("publicados", 0),
        })  # fmt: skip
    if not lista:
        return {"empresas": [], "aviso": "Nenhuma empresa cadastrada (página Empresas)."}
    return {"empresas": lista}


def ler_funil() -> dict[str, Any]:
    from zervis.redes import instagram_comentarios, instagram_direct

    c, d = instagram_comentarios.PADRAO.estado(), instagram_direct.PADRAO.estado()
    respondidos = instagram_comentarios.PADRAO.recentes(200)
    semana = datetime.now(fuso.local()).timestamp() - 7 * 86400
    contatos = sorted(d["contatos"].items(), key=lambda x: -float(x[1].get("quando", 0) or 0))
    etapas: dict[str, int] = {}
    for _usuario, contato in contatos:
        etapa = str(contato.get("etapa") or "abertura")
        etapas[etapa] = etapas.get(etapa, 0) + 1
    return {
        "comentarios_viram_conversa": "ligado" if c["ligado"] else "desligado",
        "comentarios_respondidos_7_dias": sum(
            1 for r in respondidos if float(r.get("respondido") or 0) >= semana
        ),
        "ultimos_comentarios": [
            {
                "quem": f"@{r.get('autor', '')}",
                "comentou": _curto(r.get("texto"), 120),
                "quando": _hora(r.get("quando")),
                "abertura_no_direct": "sim" if r.get("direct") else "não",
                **({"erro": r["erro"]} if r.get("erro") else {}),
            }
            for r in respondidos[:6]
        ],
        "conversa_no_direct": "ligada" if d["ligado"] else "desligada",
        "link_de_agendamento": "configurado" if d["link"] else "sem link",
        "conversas_por_etapa": etapas,
        "contas_ignoradas": len(c["ignoradas"]),
    }


def ler_atividade(busca: str, dias: int, tipo: str, quantos: int) -> dict[str, Any]:
    desde = (datetime.now(fuso.local()) - timedelta(days=dias)).timestamp()
    base = atividade.PADRAO
    brutos = base.buscar(busca, limite=500) if busca else base.listar(limite=2000)
    itens = [
        r for r in brutos
        if float(r.get("quando", 0)) >= desde and (not tipo or r.get("tipo") == tipo)
    ]  # fmt: skip
    itens.sort(key=lambda r: -float(r.get("quando", 0)))
    return {
        "total": len(itens),
        "registros": [
            {
                "quando": _hora(r.get("quando")),
                "tipo": TIPOS.get(str(r.get("tipo")), str(r.get("tipo"))),
                "o_que": _curto(r.get("titulo"), 160),
                **({"de_onde": r["origem"]} if r.get("origem") else {}),
                **({"resultado": _curto(r["resultado"], 200)} if r.get("resultado") else {}),
                **({"erro": _curto(r["erro"], 200)} if r.get("erro") else {}),
            }
            for r in itens[:quantos]
        ],
    }


def ferramentas() -> list[SdkMcpTool[Any]]:
    @tool(
        "empresas_listar",
        "As empresas que o usuário gere (a página Empresas): o grupo de WhatsApp de cada uma, se "
        "o Zé responde no grupo, a pasta do projeto e quantos arquivos há na vitrine. Só lê.",
        {"type": "object", "properties": {}},
    )
    async def empresas_listar(_args: dict[str, Any]) -> dict[str, Any]:
        return _texto(await asyncio.to_thread(ler_empresas))

    @tool(
        "redes_situacao",
        "O funil do Instagram (as páginas Redes sociais e Marketing): se os comentários viram "
        "conversa no direct, quantos foram respondidos na semana, os últimos (quem, o quê, se a "
        "abertura foi), se a conversa no direct está ligada, o link de agendamento e as conversas "
        'por etapa. Use para "quem comentou?", "o direct está respondendo?". Só lê.',
        {"type": "object", "properties": {}},
    )
    async def redes_situacao(_args: dict[str, Any]) -> dict[str, Any]:
        return _texto(await asyncio.to_thread(ler_funil))

    @tool(
        "atividade_buscar",
        "A Atividade do Zé (a página Atividade): tudo o que ele executou, com quando, o resultado "
        "e as falhas, de qualquer parte (prospecção, WhatsApp, Instagram, automações, sessões, "
        'marketing, ligações). Use para "o que aconteceu com…", "você mandou…?", "o que falhou '
        'hoje?", "o que a prospecção fez?". `busca`: palavras (ex.: "Prospecção", um nome); '
        "vazio traz os mais recentes. Só lê.",
        {
            "type": "object",
            "properties": {
                "busca": {"type": "string"},
                "dias": {"type": "integer", "description": "Os últimos N dias (1 a 30)"},
                "tipo": {"type": "string", "enum": ["", *TIPOS]},
                "quantos": {"type": "integer", "description": "Até 40"},
            },
        },
    )
    async def atividade_buscar(args: dict[str, Any]) -> dict[str, Any]:
        def inteiro(chave: str, padrao: int, maximo: int) -> int:
            v = args.get(chave)
            return max(1, min(maximo, v)) if isinstance(v, int) else padrao

        dados = await asyncio.to_thread(
            ler_atividade,
            " ".join(str(args.get("busca") or "").split())[:100],
            inteiro("dias", 7, 30),
            str(args.get("tipo") or ""),
            inteiro("quantos", 20, 40),
        )
        return _texto(dados)

    return [empresas_listar, redes_situacao, atividade_buscar]
