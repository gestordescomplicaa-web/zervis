"""Modelos 3D prontos (ADR 0049): o Zé busca num acervo livre, baixa para o Acervo e mostra em
holograma. Só lê a internet numa fonte permitida e só grava no próprio Acervo, então passa sem
perguntar; as travas do download estão em `zervis/imersivo/modelos3d.py`."""

import asyncio
import base64
import json
from pathlib import Path
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.imersivo import modelos3d
from zervis.rosto.tela import Tela, TelaErro

TIPOS_DE_IMAGEM = {b"\x89PNG": "image/png", b"\xff\xd8\xff": "image/jpeg", b"RIFF": "image/webp"}


def _tipo(imagem: bytes) -> str | None:
    if imagem[:4] == b"RIFF" and imagem[8:12] != b"WEBP":
        return None
    return next((t for m, t in TIPOS_DE_IMAGEM.items() if imagem.startswith(m)), None)


def _com_previas(dados: dict[str, Any], vistas: list[tuple[str, bytes]]) -> dict[str, Any]:
    """O resultado em texto e, depois, a prévia de cada achado, rotulada pelo id."""
    conteudo: list[dict[str, Any]] = [
        {"type": "text", "text": json.dumps(dados, ensure_ascii=False)}
    ]
    for id_, imagem in vistas:
        if tipo := _tipo(imagem):
            conteudo.append({"type": "text", "text": f"Prévia de {id_}:"})
            conteudo.append(
                {"type": "image", "data": base64.b64encode(imagem).decode(), "mimeType": tipo}
            )
    return {"content": conteudo}


def ferramentas(acervo: Path | None, tela: Tela | None) -> list[SdkMcpTool[Any]]:
    if acervo is None:
        return []

    @tool(
        "modelo3d_buscar",
        "Busca modelos 3D prontos e livres para mostrar em holograma: um objeto real e "
        "reconhecível, como cavalo, carro, avião, coração, prédio, planta; naves, sondas, "
        "foguetes e astronautas vêm oficiais da NASA (Hubble, ISS, Saturn V, space shuttle, "
        "Perseverance). Busque em inglês (horse, car, space station). Devolve cada achado com "
        "fonte, qualidade (oficial, detalhado, médio, simples; e se foi feito por IA) e, "
        "quando houver, a prévia em imagem logo depois. Olhe as prévias e escolha o que parece "
        "de verdade com o pedido; um modelo simples ou feito por IA só se não houver outro. Se "
        "nenhum prestar, diga isso em vez de mostrar um feio. Escolha em silêncio: o que você "
        "escreve entre as ferramentas é falado. Baixe com modelo3d_baixar. Para um esquema ou "
        "conceito (sistema solar, átomo, molécula), monte com o bloco holograma.",
        {
            "type": "object",
            "properties": {
                "busca": {"type": "string", "description": "Em inglês, curto: horse, red car"},
                "quantos": {"type": "integer", "description": "De 1 a 12, padrão 6"},
            },
            "required": ["busca"],
        },
    )
    async def modelo3d_buscar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            achados = await asyncio.to_thread(
                modelos3d.buscar,
                str(args.get("busca", "")),
                int(args.get("quantos") or 6),
                acervo=acervo,
            )
        except (modelos3d.ModeloErro, ValueError) as erro:
            return _erro(erro)
        if not achados:
            return _texto({"achados": [], "dica": "nada que a tela leia; tente outra palavra"})
        vistas = await asyncio.to_thread(modelos3d.previas, achados)
        return _com_previas({"achados": modelos3d.para_resposta(achados)}, vistas)

    @tool(
        "modelo3d_baixar",
        "Baixa para o Acervo o modelo que modelo3d_buscar achou (pelo id) e, com mostrar=true, já "
        "o põe na tela em holograma, num cartão que a pinça trava e gira em todos os eixos. "
        "Devolve o arquivo no Acervo, que serve depois para o bloco modelo de tela_explicar "
        "(uma explicação com o modelo ao lado) ou para tela_agir mostrar_modelo. Um modelo já "
        "baixado é reusado na hora.",
        {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "O id da busca: nasa:slug, 3dassets:slug"},
                "titulo": {"type": "string", "description": "Em português, para a tela: Cavalo"},
                "mostrar": {"type": "boolean"},
            },
            "required": ["id"],
        },
    )
    async def modelo3d_baixar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            r = await asyncio.to_thread(modelos3d.baixar, str(args.get("id", "")), acervo)
        except modelos3d.ModeloErro as erro:
            return _erro(erro)
        titulo = str(args.get("titulo") or r["titulo"])[:60]
        resposta = {
            k: r[k] for k in ("arquivo", "titulo", "licenca", "autor", "feito_por_ia", "reusado")
        }
        if args.get("mostrar"):
            if tela is None:
                resposta["mostrado"] = "tela indisponível"
            else:
                acao = {"acao": "mostrar_modelo", "alvo": r["arquivo"], "valor": titulo}
                try:
                    tela_r = await asyncio.to_thread(tela.agir, [acao])
                    res = (tela_r.get("resultados") or [{}])[0]
                    resposta["mostrado"] = bool(res.get("ok")) if isinstance(res, dict) else res
                except (TelaErro, OSError) as erro:
                    resposta["mostrado"] = f"não: {erro}"
        return _texto(resposta)

    return [modelo3d_buscar, modelo3d_baixar]
