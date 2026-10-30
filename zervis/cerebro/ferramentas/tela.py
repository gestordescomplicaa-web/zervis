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
TIPOS += ["globo", "mapa", "comparar", "lista", "linha_tempo", "holograma", "modelo"]
PECAS = ["esfera", "cubo", "caixa", "cilindro", "cone", "piramide", "toro", "anel", "capsula"]
PECAS += ["helice", "tubo", "linha", "ligacao", "particulas"]


def _texto_(descricao: str = "") -> dict[str, Any]:
    return {"type": "string", **({"description": descricao} if descricao else {})}


def _num(descricao: str = "") -> dict[str, Any]:
    return {"type": "number", **({"description": descricao} if descricao else {})}


def _lista_de(descricao: str, **campos: dict[str, Any]) -> dict[str, Any]:
    item = {"type": "object", "properties": campos}
    return {"type": "array", "description": descricao, "items": item}


def _peca(com_filhos: bool) -> dict[str, Any]:
    trio = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}
    props: dict[str, Any] = {
        "forma": {"type": "string", "enum": PECAS},
        "nome": _texto_(),
        "rotulo": _texto_("texto que flutua sobre a peça"),
        "cor": _texto_(
            "#rrggbb ou azul, vermelho, verde, amarelo, laranja, roxo, rosa, branco, "
            "ciano, dourado, cinza, marrom, prata"
        ),
        "pos": {**trio, "description": "[x, y, z] em relação ao pai"},
        "tam": {
            **trio,
            "description": "[largura, altura, profundidade]; esfera: o diâmetro nos três",
        },
        "rot": {**trio, "description": "[x, y, z] em graus"},
        "anim": {"type": "string", "enum": ["girar", "pulsar", "flutuar", "orbitar"]},
        "velocidade": _num("1 é o normal"),
        "orbita": {
            "type": "object",
            "description": "gira em volta do centro do pai",
            "properties": {
                "raio": _num(),
                "velocidade": _num("1 = uma volta a cada 8 s"),
                "inclinacao": _num("graus"),
                "trilha": {"type": "boolean"},
            },
        },
        "de": {**trio, "description": "ligacao: um ponta"},
        "ate": {**trio, "description": "ligacao: a outra ponta (o cilindro se orienta sozinho)"},
        "pontos": {"type": "array", "items": trio, "description": "tubo e linha: o caminho"},
        "voltas": _num("helice"),
        "espessura": _num("toro, anel, helice, tubo e ligacao: 0.01 a 1"),
        "quantidade": _num("particulas: até 3000, numa nuvem do tamanho de tam"),
    }
    if com_filhos:
        props["filhos"] = {"type": "array", "items": _peca(False)}
    return {"type": "object", "properties": props, "required": ["forma"]}


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
        "unidade": _texto_("numero, barras, linha, mapa"),
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
            "linha: [{rotulo, valor}] em ordem; globo e mapa: cidades [{nome, lat, lon}], a "
            "primeira é a origem dos arcos",
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
        "ligar": {
            "type": "boolean",
            "description": "globo e mapa: arcos do primeiro ponto aos outros",
        },
        "regiao": _texto_(
            "mapa: o que enquadrar. brasil (os 27 estados), norte, nordeste, centro-oeste, "
            "sudeste, sul (estados), mundo, america do sul, america do norte, america central, "
            "europa, africa, asia, oriente medio, oceania (países), ou um país pelo nome (ele e "
            "os vizinhos)"
        ),
        "destaques": _lista_de(
            "mapa: o que acender, pelo nome ou sigla (SP, Bahia, Argentina, Nordeste). Com "
            "valor, vira um mapa de calor (mais claro = maior) e leva fonte ou ilustrativo",
            nome=NOME,
            valor=_num(),
            rotulo=_texto_("o texto no mapa, se não for o nome"),
        ),
        "isolar": {
            "type": "boolean",
            "description": "mapa: mostra só a região ou os destaques, sem o resto do país ou do "
            'mundo em volta ("só o Nordeste")',
        },
        "relevo": {
            "type": "boolean",
            "description": "mapa: em 3D, cada lugar sobe pela altura do valor, num cartão que a "
            "mão gira",
        },
        "lados": {
            "type": "array",
            "description": "comparar: exatamente dois",
            "items": {
                "type": "object",
                "properties": {"nome": NOME, "itens": {"type": "array", "items": _texto_()}},
            },
        },
        "marcos": _lista_de("linha_tempo: em ordem", quando=TEXTO, nome=NOME),
        "arquivo": _texto_("modelo: o arquivo no Acervo que modelo3d_baixar devolveu"),
        "estilo": {
            "type": "string",
            "enum": ["holograma", "solido"],
            "description": "holograma: vidro holográfico com as cores das peças (padrão); solido: "
            "material de verdade",
        },
        "pecas": {
            "type": "array",
            "description": "holograma: o objeto 3D montado com peças (até 80), na unidade que "
            "quiser (a tela enquadra). Use filhos para o que se move junto (a Lua na Terra).",
            "items": _peca(True),
        },
    },
    "required": ["tipo"],
}


def ferramentas(tela: Tela | None) -> list[SdkMcpTool[Any]]:
    @tool(
        "tela_ver",
        "O que está na sua tela agora: o Núcleo (as telas do manifesto, painéis, notas e "
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
        "Mexe na sua tela, em ordem e com animação, numa chamada só: abrir exatamente uma tela "
        "do Núcleo (os orbes do manifesto) ou qualquer item dela pelo "
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
        "inventado como medido. Objeto real em 3D (cavalo, carro): modelo3d_buscar e "
        "modelo3d_baixar, e o bloco modelo com o arquivo. Esquema ou conceito em 3D (sistema "
        "solar, átomo): bloco holograma, montado com peças (forma3d é só um desenho). Mapa "
        "(do Brasil, de estados, países, continentes, onde fica algo): bloco mapa, com regiao, "
        "destaques pelo nome e cidades com lat/lon; os contornos são reais, então nunca desenhe "
        "mapa com peças, forma3d ou globo (relevo=true para o mapa em 3D). Para "
        "conceito, prefira etapas, rede, onda, comparar e "
        'lista. Para tirar a cena ("tira isso", "limpa a tela"): tela_agir fechar com alvo cena.',
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
        "o usuário quiser ver algo na tela. Com ela aberta, mostrar algo é tela_agir.",
        {},
    )
    async def janela_abrir(_: dict[str, Any]) -> dict[str, Any]:
        if tela is None:
            return _erro(ValueError("tela do Zé indisponível"))
        await asyncio.to_thread(tela.abrir)
        return _texto({"aberto": await asyncio.to_thread(tela.aberto)})

    @tool(
        "janela_fechar",
        "Fecha a janela do Zé (a câmera apaga). Para fechar só uma tela, use tela_agir.",
        {},
    )
    async def janela_fechar(_: dict[str, Any]) -> dict[str, Any]:
        if tela is None:
            return _erro(ValueError("tela do Zé indisponível"))
        await asyncio.to_thread(tela.fechar)
        return _texto({"aberto": False})

    return [tela_ver, tela_agir, tela_explicar, janela_abrir, janela_fechar]
