"""Ferramentas da tela: o Zé vê e mexe no Núcleo e abre ou fecha a própria janela."""

import asyncio
import json
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.rosto.tela import ACOES as ACOES_DA_TELA
from zervis.rosto.tela import CENA, Tela, TelaErro

TAMANHO_DA_CENA = 16_000  # caracteres do JSON; a página ainda limita passos e blocos
BLOCOS = (
    "titulo{texto,subtitulo}; numero{valor,unidade,prefixo,rotulo,detalhe,de (o total, desenha o "
    "anel cheio até valor/de)}; barras{itens:[{nome,valor}],unidade}; "
    "linha{pontos:[{rotulo,valor}],unidade}; rosca{fatias:[{nome,valor}],centro}; "
    "etapas{etapas:[{nome,texto}]} (2 a 6); rede{centro,nos:[{nome,texto}]}; "
    "onda{ondas:[{nome,frequencia 0.3 a 8,amplitude 0 a 1}],soma}; forma3d{forma: esfera, toro, "
    "helice (DNA), cubo, atomo, galaxia, terreno (superfície ondulando), neural (camadas ligadas) "
    "ou plexo (rede de pontos), legenda}; globo{pontos:[{nome,lat,lon}],ligar (arcos do primeiro "
    "aos outros)}; comparar{lados:[{nome,itens:[texto]}] (dois)}; lista{itens:[texto]}; "
    "linha_tempo{marcos:[{quando,nome}]}"
)


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
            return _erro(ValueError("tela do Zé indisponível"))
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
            return _erro(ValueError("tela do Zé indisponível"))
        try:
            resposta = await asyncio.to_thread(
                tela.agir, list(args["acoes"]), bool(args.get("trazer", True))
            )
        except (TelaErro, OSError) as erro:
            return _erro(erro)
        return _texto({k: resposta.get(k) for k in ("resultados", "estado")})

    @tool(
        "tela_explicar",
        "Explica algo com uma cena animada na sua tela: você vai para o canto e os blocos "
        "(gráficos, ondas, formas 3D, globo, etapas) aparecem um a um, ligados a você por feixes, "
        "com a fala de cada passo como legenda. Use quando o usuário pedir para explicar, ensinar "
        "ou mostrar um assunto e a janela estiver aberta. De 2 a 6 passos; cada passo tem fala "
        "(curta, as mesmas frases que você diz, na mesma ordem) e até 4 blocos; a tela pagina "
        "sozinha (limpar=true começa uma página nova). O primeiro passo costuma ter um titulo. "
        "Todo bloco aceita titulo. Tipos: "
        + BLOCOS
        + ". Números (numero, barras, linha, rosca) levam fonte (de onde vêm: seus dados, a "
        "pesquisa, um valor de referência) ou ilustrativo=true; nunca mostre número inventado "
        "como medido. Para conceito, prefira etapas, rede, onda, forma3d, comparar e lista. A "
        "tecla A ou outra cena tira esta.",
        {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "passos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "fala": {"type": "string"},
                            "limpar": {"type": "boolean"},
                            "blocos": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "tipo": {
                                            "type": "string",
                                            "enum": [
                                                "titulo",
                                                "numero",
                                                "barras",
                                                "linha",
                                                "rosca",
                                                "etapas",
                                                "rede",
                                                "onda",
                                                "forma3d",
                                                "globo",
                                                "comparar",
                                                "lista",
                                                "linha_tempo",
                                            ],
                                        },
                                        "titulo": {"type": "string"},
                                        "fonte": {"type": "string"},
                                        "ilustrativo": {"type": "boolean"},
                                    },
                                    "required": ["tipo"],
                                },
                            },
                        },
                    },
                },
                "trazer": {"type": "boolean"},
            },
            "required": ["titulo", "passos"],
        },
    )
    async def tela_explicar(args: dict[str, Any]) -> dict[str, Any]:
        if tela is None:
            return _erro(ValueError("tela do Zé indisponível"))
        cena = {"titulo": str(args.get("titulo", "")), "passos": args.get("passos")}
        if not isinstance(cena["passos"], list) or not cena["passos"]:
            return _erro(ValueError("a cena precisa de passos"))
        if len(json.dumps(cena, ensure_ascii=False)) > TAMANHO_DA_CENA:
            return _erro(ValueError("cena grande demais: menos passos ou blocos"))
        try:
            resposta = await asyncio.to_thread(
                tela.agir, [{"acao": CENA, "cena": cena}], bool(args.get("trazer", True))
            )
        except (TelaErro, OSError) as erro:
            return _erro(erro)
        return _texto({k: resposta.get(k) for k in ("resultados",)})

    @tool(
        "janela_abrir",
        "Abre a janela do Zé (a câmera acende) quando o resumo disser que ela está fechada e "
        "o usuário quiser ver algo na tela. Para abrir o Núcleo com ela aberta, use tela_agir.",
        {},
    )
    async def janela_abrir(_: dict[str, Any]) -> dict[str, Any]:
        if tela is None:
            return _erro(ValueError("tela do Zé indisponível"))
        await asyncio.to_thread(tela.abrir)
        return _texto({"aberto": await asyncio.to_thread(tela.aberto)})

    @tool(
        "janela_fechar",
        "Fecha a janela do Zé (a câmera apaga). Para só recolher o Núcleo, use tela_agir.",
        {},
    )
    async def janela_fechar(_: dict[str, Any]) -> dict[str, Any]:
        if tela is None:
            return _erro(ValueError("tela do Zé indisponível"))
        await asyncio.to_thread(tela.fechar)
        return _texto({"aberto": False})

    return [tela_ver, tela_agir, tela_explicar, janela_abrir, janela_fechar]
