"""Ferramentas da tela: o Zé vê e mexe no Núcleo e abre ou fecha a própria janela."""

import asyncio
import json
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.rosto.tela import ACOES as ACOES_DA_TELA
from zervis.rosto.tela import CENA, Tela, TelaErro

TAMANHO_DA_CENA = 16_000  # caracteres do JSON; a página ainda limita passos e blocos
FORMAS = ["esfera", "toro", "helice", "cubo", "atomo", "galaxia", "terreno", "neural", "plexo"]
TIPOS = ["titulo", "numero", "barras", "linha", "rosca", "etapas", "rede", "onda", "forma3d"]
TIPOS += ["globo", "comparar", "lista", "linha_tempo"]


def _texto_(descricao: str = "") -> dict[str, Any]:
    return {"type": "string", **({"description": descricao} if descricao else {})}


def _num(descricao: str = "") -> dict[str, Any]:
    return {"type": "number", **({"description": descricao} if descricao else {})}


def _lista_de(descricao: str, **campos: dict[str, Any]) -> dict[str, Any]:
    item = {"type": "object", "properties": campos}
    return {"type": "array", "description": descricao, "items": item}


NOME, TEXTO = _texto_(), _texto_()
# Cada campo diz a que tipo serve: é o esquema que o modelo segue à risca, então o conteúdo de
# todos os blocos tem de estar aqui (sem ele, o modelo manda só o tipo e o título).
BLOCO: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tipo": {"type": "string", "enum": TIPOS},
        "titulo": _texto_("o nome do painel"),
        "fonte": _texto_("de onde vêm os números: seus dados, a pesquisa, valor de referência"),
        "ilustrativo": {"type": "boolean", "description": "números de exemplo, não medidos"},
        "texto": _texto_("titulo: a frase grande"),
        "subtitulo": _texto_("titulo"),
        "valor": _num("numero: o valor"),
        "de": _num("numero: o total (o anel enche até valor/de)"),
        "unidade": _texto_("numero, barras, linha"),
        "prefixo": _texto_("numero: R$, US$"),
        "rotulo": _texto_("numero: o que o número mede"),
        "detalhe": _texto_("numero: uma frase curta"),
        "itens": {
            "type": "array",
            "description": "barras: [{nome, valor}]; lista: [texto]",
            "items": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "object", "properties": {"nome": NOME, "valor": _num()}},
                ]
            },
        },
        "pontos": _lista_de(
            "linha: [{rotulo, valor}] em ordem; globo: [{nome, lat, lon}], o primeiro é a origem",
            rotulo=TEXTO,
            valor=_num(),
            nome=NOME,
            lat=_num(),
            lon=_num(),
        ),
        "fatias": _lista_de("rosca: [{nome, valor}]", nome=NOME, valor=_num()),
        "centro": _texto_("rosca: o texto no meio; rede: o nó central"),
        "etapas": _lista_de("etapas: 2 a 6, em ordem", nome=NOME, texto=TEXTO),
        "nos": _lista_de("rede: até 10, em volta do centro", nome=NOME, texto=TEXTO),
        "ondas": _lista_de(
            "onda: até 3",
            nome=NOME,
            frequencia=_num("0.3 a 8, relativa"),
            amplitude=_num("0 a 1"),
        ),
        "soma": {"type": "boolean", "description": "onda: desenha a soma das ondas"},
        "forma": {
            "type": "string",
            "enum": FORMAS,
            "description": "forma3d: helice é o DNA; terreno, uma superfície ondulando; neural, "
            "camadas ligadas; plexo, uma rede de pontos",
        },
        "legenda": _texto_("forma3d: uma frase embaixo"),
        "ligar": {"type": "boolean", "description": "globo: arcos do primeiro ponto aos outros"},
        "lados": {
            "type": "array",
            "description": "comparar: exatamente dois",
            "items": {
                "type": "object",
                "properties": {"nome": NOME, "itens": {"type": "array", "items": _texto_()}},
            },
        },
        "marcos": _lista_de("linha_tempo: em ordem", quando=TEXTO, nome=NOME),
    },
    "required": ["tipo"],
}


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
        "Preencha o conteúdo de cada bloco nos campos do tipo dele (o esquema diz qual campo é "
        "de qual tipo). Números (numero, barras, linha, rosca) levam fonte (de onde vêm: seus "
        "dados, a pesquisa, um valor de referência) ou ilustrativo=true; nunca mostre número "
        "inventado como medido. Para conceito, prefira etapas, rede, onda, forma3d, comparar e "
        "lista. A tecla A ou outra cena tira esta.",
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
                            "blocos": {"type": "array", "items": BLOCO},
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
