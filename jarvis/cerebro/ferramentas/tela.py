"""Ferramentas da tela: o JARVIS vê e mexe no Núcleo e abre ou fecha a própria janela."""

import asyncio
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from jarvis.cerebro.ferramentas.comum import _erro, _texto
from jarvis.rosto.tela import ACOES as ACOES_DA_TELA
from jarvis.rosto.tela import Tela, TelaErro


def ferramentas(tela: Tela | None) -> list[SdkMcpTool[Any]]:
    @tool(
        "tela_ver",
        "O que está na sua tela agora: o Núcleo (aberto ou recolhido, orbes, painéis, notas e "
        "arquivos abertos), o Mapa aberto e a vista (geral, trabalho, foco), item em foco, zoom, "
        "áreas e itens com nome e id, menu de configurações, tema, brilho da câmera, mãos e "
        "câmera, se o usuário está usando as mãos e se a janela é a ativa. O resumo de cada "
        "pedido já diz o essencial; use esta só para nomes e ids.",
        {},
    )
    async def tela_ver(_: dict[str, Any]) -> dict[str, Any]:
        if tela is None:
            return _erro(ValueError("tela do JARVIS indisponível"))
        try:
            return _texto(await asyncio.to_thread(tela.ver))
        except (TelaErro, OSError) as erro:
            return _erro(erro)

    @tool(
        "tela_agir",
        "Mexe na sua tela, em ordem e com animação, numa chamada só: abrir ou recolher o Núcleo "
        "(o anel com os orbes do manifesto), abrir exatamente um orbe ou qualquer item dele pelo "
        "nome falado ('burrinho' acha o arquivo do Acervo), buscar por nome, fechar, a vista do "
        "Mapa, focar, zoom, mover, rolar, menu de configurações, teclado, tema, brilho da câmera, "
        "calibrar as mãos. Só quando o usuário pedir para ver ou mudar algo no Núcleo. Para um "
        "passeio, intercale 'aguardar'; voltam logo e seguem na tela enquanto você fala. Traz a "
        "janela para a frente (trazer=false para não trazer). Ações: "
        + "; ".join(f"{nome} ({faz})" for nome, faz in ACOES_DA_TELA.items()),
        {
            "type": "object",
            "properties": {
                "acoes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "acao": {"type": "string", "enum": sorted(ACOES_DA_TELA)},
                            "alvo": {"type": "string"},
                            "orbe": {
                                "type": "string",
                                "description": "Onde procurar (abrir, buscar)",
                            },
                            "valor": {"type": ["string", "number"]},
                        },
                        "required": ["acao"],
                    },
                },
                "trazer": {"type": "boolean"},
            },
            "required": ["acoes"],
        },
    )
    async def tela_agir(args: dict[str, Any]) -> dict[str, Any]:
        if tela is None:
            return _erro(ValueError("tela do JARVIS indisponível"))
        try:
            resposta = await asyncio.to_thread(
                tela.agir, list(args["acoes"]), bool(args.get("trazer", True))
            )
        except (TelaErro, OSError) as erro:
            return _erro(erro)
        return _texto({k: resposta.get(k) for k in ("resultados", "estado")})

    @tool(
        "janela_abrir",
        "Abre a janela do JARVIS (a câmera acende) quando o resumo disser que ela está fechada e "
        "o usuário quiser ver algo na tela. Para abrir o Núcleo com ela aberta, use tela_agir.",
        {},
    )
    async def janela_abrir(_: dict[str, Any]) -> dict[str, Any]:
        if tela is None:
            return _erro(ValueError("tela do JARVIS indisponível"))
        await asyncio.to_thread(tela.abrir)
        return _texto({"aberto": await asyncio.to_thread(tela.aberto)})

    @tool(
        "janela_fechar",
        "Fecha a janela do JARVIS (a câmera apaga). Para só recolher o Núcleo, use tela_agir.",
        {},
    )
    async def janela_fechar(_: dict[str, Any]) -> dict[str, Any]:
        if tela is None:
            return _erro(ValueError("tela do JARVIS indisponível"))
        await asyncio.to_thread(tela.fechar)
        return _texto({"aberto": False})

    return [tela_ver, tela_agir, janela_abrir, janela_fechar]
