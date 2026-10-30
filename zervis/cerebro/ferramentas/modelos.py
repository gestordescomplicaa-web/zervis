"""Modelos 3D prontos (ADR 0049): o Zé busca num acervo livre, baixa para o Acervo e mostra em
holograma. Só lê a internet numa fonte permitida e só grava no próprio Acervo, então passa sem
perguntar; as travas do download estão em `zervis/imersivo/modelos3d.py`."""

import asyncio
from pathlib import Path
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.imersivo import modelos3d
from zervis.rosto.tela import Tela, TelaErro


def ferramentas(acervo: Path | None, tela: Tela | None) -> list[SdkMcpTool[Any]]:
    if acervo is None:
        return []

    @tool(
        "modelo3d_buscar",
        "Busca modelos 3D prontos e livres (CC0) para mostrar em holograma: um objeto real e "
        "reconhecível, como cavalo, carro, avião, coração, prédio, planta. Busque em inglês "
        "(horse, car, airplane): a fonte é em inglês. Devolve id, título, resumo, licença, "
        "triângulos (mais é mais detalhado) e se foi feito por IA; escolha o que corresponde ao "
        "pedido e "
        "baixe com modelo3d_baixar. Para um esquema ou conceito (sistema solar, átomo, molécula), "
        "monte com o bloco holograma em vez disso.",
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
                modelos3d.buscar, str(args.get("busca", "")), int(args.get("quantos") or 6)
            )
        except (modelos3d.ModeloErro, ValueError) as erro:
            return _erro(erro)
        if not achados:
            return _texto({"achados": [], "dica": "nada que a tela leia; tente outra palavra"})
        return _texto({"achados": modelos3d.para_resposta(achados)})

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
                "id": {"type": "string", "description": "O id da busca, como 3dassets:slug"},
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
