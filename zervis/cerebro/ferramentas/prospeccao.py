"""A Prospecção pela voz (ADR 0127 e 0128): o que está acontecendo e o que fazer com cada empresa.

Ler (`prospeccao_situacao`) passa sem perguntar; aprovar, descartar, adiantar, buscar e ajustar
mudam o que sai pelo WhatsApp de quem usa, então passam pela aprovação falada. A Prospecção cuida
da primeira mensagem (ADR 0140): a conversa depois dela quem usa faz no WhatsApp. Nomes,
avaliações e respostas das empresas são texto de terceiros: a leitura conta como "de fora".
"""

import asyncio
import re
from datetime import datetime
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis import fuso
from zervis.cerebro.ferramentas.comum import _texto
from zervis.prospeccao import funil, por_ramo

EMPRESA = {"type": "string", "description": "O nome da empresa ou do dono, ou o id"}


def _erro(texto: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": texto}], "is_error": True}


def _hora(quando: Any) -> str:
    if not quando:
        return ""
    return datetime.fromtimestamp(float(quando), fuso.local()).strftime("%d/%m %H:%M")


def _empresa(p: dict[str, Any], inteira: bool = False) -> dict[str, Any]:
    lugar = p.get("lugar") or {}
    resumo = {
        "id": p["id"],
        "empresa": p["nome"],
        "estado": funil.ROTULOS.get(p["status"], p["status"]),
        "quem_decide": f"{p['dono']} ({p['cargo']})" if p.get("dono") else "",
        "nota": p.get("nota") or None,
        "por_que": p.get("sinal") or p.get("motivo") or "",
        "enviada_em": _hora(p.get("enviado")),
        "resposta": p.get("resposta", ""),
    }
    if inteira:
        resumo |= {
            "ramo": lugar.get("categoria") or (p.get("cadastro") or {}).get("atividade", ""),
            "telefones": [f"{t['numero']} ({t['origem']})" for t in p.get("telefones", [])],
            "enviada_para": p.get("telefone_enviado", ""),
            "mensagem": p.get("mensagem", ""),
            "notas": p.get("notas", {}),
            "maps": lugar.get("link", ""),
            "cnpj": (p.get("cadastro") or {}).get("cnpj", ""),
            "erro": p.get("erro", ""),
        }
    return {k: v for k, v in resumo.items() if v not in ("", None, [], {})}


def _motivo(texto: str) -> str:
    """O motivo sem a nota ("Nota 38: pouco sinal." vira "Pouco sinal"), para contar junto."""
    curto = re.sub(r"^Nota \d+:\s*", "", str(texto or "")).strip().rstrip(".")
    return curto[:1].upper() + curto[1:] if curto else "Sem motivo"


def descartadas(todas: list[dict[str, Any]]) -> dict[str, int]:
    contagem: dict[str, int] = {}
    for p in todas:
        if p.get("status") == "descartada":
            m = _motivo(p.get("motivo", ""))
            contagem[m] = contagem.get(m, 0) + 1
    return dict(sorted(contagem.items(), key=lambda x: -x[1]))


def situacao(f: funil.Funil, empresa: str = "") -> dict[str, Any]:
    if empresa:
        return {"empresa": _empresa(f.achar(empresa), inteira=True)}
    tela = f.para_tela()
    cfg = tela["config"]
    todas = sorted(f.todas(), key=lambda p: -float(p.get("atualizado", 0)))
    enviando = [p for p in todas if p.get("status") == "enviando"]
    return {
        "estado": "Ligada" if cfg["ligada"] else "Desligada",
        "aviso": tela["erro"],
        "enviar_sozinho": cfg["sozinho"],
        "cidade": cfg["cidade"],
        "ramos": cfg["ramos"],
        "hoje": f"{tela['hoje']['enviadas']} de {tela['hoje']['limite']} enviadas",
        "proximo_envio": tela["proximo"],
        "horario": tela["horario"],
        "agora": (
            "buscando ou qualificando empresas"
            if tela["ocupado"]
            else f"envio não confirmado para {enviando[0]['nome']}"
            if enviando
            else "nada em andamento"
        ),
        "contagem": {funil.ROTULOS[k]: v for k, v in tela["contagem"].items() if v},
        "aguardando_aprovacao": [
            {**_empresa(p), "mensagem": p.get("mensagem", "")}
            for p in todas
            if p["status"] == "aprovar"
        ][:8],
        "recentes": [
            {**_empresa(p), "ramo": por_ramo.ramo_de(p, cfg["ramos"])}
            for p in todas
            if p["status"] not in ("aprovar", "descartada")
        ][:10],
        "descartadas": descartadas(todas),
        "google_maps": "configurado" if tela["apify"] else "sem a chave da Apify",
    }


def ferramentas() -> list[SdkMcpTool[Any]]:
    @tool(
        "prospeccao_situacao",
        "A Prospecção do Zé (a página Prospecção): se está ligada, quantas mensagens saíram hoje "
        "e quando sai a próxima, se há busca ou envio acontecendo agora, as empresas esperando "
        "aprovação (com a mensagem), as contatadas por ramo, quem respondeu e quantas foram "
        "descartadas por motivo. Com `empresa`, tudo de uma (também uma descartada): quem decide, "
        "telefones, nota, mensagem e resposta. "
        'Use para "está havendo disparo?", "como está a prospecção?", "quem respondeu?". Só lê.',
        {"type": "object", "properties": {"empresa": EMPRESA}},
    )
    async def prospeccao_situacao(args: dict[str, Any]) -> dict[str, Any]:
        try:
            dados = await asyncio.to_thread(
                situacao, funil.padrao(), str(args.get("empresa") or "")
            )
        except funil.ProspeccaoErro as erro:
            return _erro(str(erro))
        return _texto(dados)

    async def _fazer(acao: Any, feito: str) -> dict[str, Any]:
        try:
            p = await asyncio.to_thread(acao)
        except funil.ProspeccaoErro as erro:
            return _erro(str(erro))
        if isinstance(p, str):
            return _texto(p)  # a ação já disse o que fez
        return _texto(feito.format(nome=p["nome"]) if isinstance(p, dict) else feito)

    @tool(
        "prospeccao_aprovar",
        "Aprova a mensagem de uma empresa que espera aprovação: ela vai para a fila e sai no "
        "próximo horário de envio. Com `texto`, troca a mensagem antes (o que o usuário ditou).",
        {
            "type": "object",
            "properties": {"empresa": EMPRESA, "texto": {"type": "string"}},
            "required": ["empresa"],
        },
    )
    async def prospeccao_aprovar(args: dict[str, Any]) -> dict[str, Any]:
        f = funil.padrao()
        return await _fazer(
            lambda: f.aprovar(
                f.achar(str(args.get("empresa", "")))["id"], str(args.get("texto") or "")
            ),
            "{nome} aprovada: sai no próximo horário de envio.",
        )

    @tool(
        "prospeccao_descartar",
        "Descarta uma empresa da prospecção (esperando aprovação ou na fila): ela não recebe "
        "mensagem e não volta.",
        {"type": "object", "properties": {"empresa": EMPRESA}, "required": ["empresa"]},
    )
    async def prospeccao_descartar(args: dict[str, Any]) -> dict[str, Any]:
        f = funil.padrao()
        return await _fazer(
            lambda: f.descartar(f.achar(str(args.get("empresa", "")))["id"]), "{nome} descartada."
        )

    @tool(
        "prospeccao_enviar_agora",
        'Adianta um envio ("manda a próxima agora"): a primeira da fila sai já, sem esperar o '
        "horário sorteado, dentro do limite do dia e do horário de envio. Para adiantar a "
        "prospecção use esta, nunca o whatsapp_enviar: por fora, a empresa não fica marcada e "
        "não conta no limite.",
        {"type": "object", "properties": {}},
    )
    async def prospeccao_enviar_agora(_args: dict[str, Any]) -> dict[str, Any]:
        return await _fazer(funil.padrao().enviar_agora, "")

    @tool(
        "prospeccao_buscar",
        "Busca empresas novas no Google Maps agora (um ramo da lista, pela Apify, que cobra por "
        "empresa) e já as qualifica. Leva alguns minutos; o resultado aparece na situação.",
        {"type": "object", "properties": {}},
    )
    async def prospeccao_buscar(_args: dict[str, Any]) -> dict[str, Any]:
        return await _fazer(funil.padrao().buscar_agora, "Busca iniciada.")

    @tool(
        "prospeccao_ajustar",
        "Muda a Prospecção: ligar ou desligar, enviar sozinho (sem aprovar cada mensagem), "
        f"envios por dia (1 a {funil.POR_DIA_MAXIMO}), a cidade e os ramos. Só o que o usuário "
        "pediu; o resto fica como está.",
        {
            "type": "object",
            "properties": {
                "ligada": {"type": "boolean"},
                "enviar_sozinho": {"type": "boolean"},
                "por_dia": {"type": "integer"},
                "cidade": {"type": "string"},
                "ramos": {"type": "array", "items": {"type": "string"}},
            },
        },
    )
    async def prospeccao_ajustar(args: dict[str, Any]) -> dict[str, Any]:
        def ajustar() -> str:
            f = funil.padrao()
            cfg = f.config()
            if isinstance(args.get("ligada"), bool):
                cfg.ligada = args["ligada"]
            if isinstance(args.get("enviar_sozinho"), bool):
                cfg.sozinho = args["enviar_sozinho"]
            if isinstance(args.get("por_dia"), int):
                cfg.por_dia = args["por_dia"]
            if isinstance(args.get("cidade"), str) and args["cidade"].strip():
                cfg.cidade = " ".join(args["cidade"].split())[:80]
            if isinstance(args.get("ramos"), list):
                cfg.ramos = [
                    " ".join(str(r).split())[:60] for r in args["ramos"][:20] if str(r).strip()
                ]
            funil.salvar_config(cfg, f.config_arquivo)
            estado = "ligada" if cfg.ligada else "desligada"
            modo = "envia sozinho" if cfg.sozinho else "cada mensagem espera aprovação"
            cidade = cfg.cidade or "cidade não definida"
            return f"Prospecção {estado}, {modo}, até {cfg.por_dia} por dia, em {cidade}."

        return await _fazer(ajustar, "")

    return [
        prospeccao_situacao,
        prospeccao_aprovar,
        prospeccao_descartar,
        prospeccao_enviar_agora,
        prospeccao_buscar,
        prospeccao_ajustar,
    ]
