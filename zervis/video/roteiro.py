"""O plano de direção de um vídeo (ADR 0106 e 0107): o modelo dirige, num formato fechado, e o Zé
confere.

O modelo nunca escreve HTML nem código. Ele pensa como diretor: define o objetivo e o público,
divide a fala em cenas e, para cada uma, escolhe o tipo, a composição, o movimento de câmera, a
transição e em que palavra da fala cada elemento entra. Aqui tudo é conferido, cortado nos limites
e só então vai para a página (que mostra o texto como texto). Uma cena fora do formato derruba o
plano: ele volta uma vez ao modelo com o motivo.

**A tela não repete a fala.** Nas cenas de texto (gancho e frase) a própria fala é a tipografia,
palavra por palavra, no tempo da voz; nas cenas visuais, a legenda acompanha embaixo e a tela
mostra só a ideia, em poucas palavras.
"""

import itertools
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from zervis.video import biblioteca, formatos
from zervis.video.estilos import Estilo

FALA_PALAVRAS = 16  # uma frase curta por cena: o corte a cada 2 a 4 segundos (ADR 0113)
# o ritmo medido, com os respiros entre as cenas (Fish S2.1 Pro e Drama 3, 23/11/2026: de 1,95
# a 2,12 em seis vídeos); as pausas longas saem do tempo antes da conta
PALAVRAS_POR_SEGUNDO = 2.0
LONGAS = 3  # pausas longas no vídeo, no máximo
PAUSA_LONGA_S = 0.8  # o mesmo de narracao.PAUSA_LONGA_S
LIMITE_LEGENDA = 2200
# A duração pedida -> (mínimo, máximo) de cenas.
DURACOES: dict[int, tuple[int, int]] = {15: (4, 6), 30: (6, 10), 45: (8, 13), 60: (10, 16)}
DURACAO_PADRAO = 30
CAMERAS = ("empurra", "afasta", "desliza", "parado")
TRANSICOES = ("corte", "mascara", "deslize", "zoom", "cor", "carta", "baralho", "cubo", "fatias")
FUNDOS = ("escuro", "claro", "cor")
# cenas que enumeram (o "passo 1, 2, 3"): duas no vídeo, no máximo (ADR 0123)
ENUMERADOS = ("item", "passos", "lista")
MAXIMO_ENUMERADOS = 2
FLUXOS = ("conexao", "hub")  # a solução do "caso" é mostrada andando (ADR 0123)
DE_TEXTO = ("gancho", "frase")  # a fala é a tipografia; sem legenda embaixo
ABERTURAS = ("gancho", "foto", "numero", "frase")  # o que pode abrir o vídeo
CORTES_PALAVRAS = 9  # "cortes": uma palavra por tela só cabe numa fala curta

# Cada tipo: os campos de texto (com o limite), as listas (mínimo, máximo, limite de cada item),
# as composições e o que o modelo lê sobre ele.
TIPOS: dict[str, dict[str, Any]] = {
    "gancho": {
        "textos": {"rotulo": 28, "destaque": 40, "foto": 80},
        "composicoes": ("centro", "esquerda", "gigante", "cortes", "carimbo"),
        "formato": '{"tipo": "gancho", "fala": "...", "destaque": "1 a 3 palavras da fala em cor", '
        '"rotulo": "opcional, até 28 (o assunto, em cápsula)", "composicao": '
        '"centro|esquerda|gigante|cortes|carimbo", "foto": "opcional: a foto que enche a tela '
        'atrás da frase (busca: <em inglês> ou uma foto da marca)"} (a fala aparece na tela, '
        'animada; não escreva outro texto; com "foto", a frase vem clara sobre a imagem: o '
        'gancho mais forte; "gigante" é uma palavra por linha, enorme, para até 7 palavras; '
        '"cortes" põe cada palavra sozinha na tela inteira, num corte seco a cada palavra, '
        'para até 9; "carimbo" faz o destaque bater na tela como um carimbo, com tremor)',
    },
    "frase": {
        "textos": {"destaque": 40},
        "composicoes": ("centro", "esquerda", "cheia", "cortes", "carimbo"),
        "formato": '{"tipo": "frase", "fala": "...", "destaque": "...", '
        '"composicao": "centro|esquerda|cheia|cortes|carimbo"} (a fala vira a tipografia; para '
        'uma afirmação forte; "cheia" pinta a tela inteira com a cor da marca; "cortes" e '
        '"carimbo" como no gancho)',
    },
    "passos": {
        "textos": {"titulo": 32},
        "listas": {"passos": (2, 4, 38)},
        "composicoes": ("vertical",),
        "formato": '{"tipo": "passos", "fala": "...", "titulo": "até 32, sem repetir a fala", '
        '"passos": [{"texto": "até 38", "quando": "a palavra da fala em que ele entra"}]} '
        "(2 a 4)",
    },
    "antes_depois": {
        "textos": {"titulo": 32, "antes": 60, "depois": 60, "quando": 30},
        "composicoes": ("empilhado", "dividido"),
        "formato": '{"tipo": "antes_depois", "fala": "...", "antes": "até 60", '
        '"depois": "até 60", "quando": "a palavra da fala em que o depois entra", '
        '"composicao": "empilhado|dividido"}',
    },
    "conversa": {
        "mensagens": (2, 4, 70),
        "composicoes": ("janela",),
        "formato": '{"tipo": "conversa", "fala": "...", "mensagens": [{"de": "cliente" ou '
        '"empresa", "texto": "até 70", "quando": "palavra da fala"}]} (2 a 4; sempre um '
        "exemplo, nunca uma conversa real)",
    },
    "lista": {
        "textos": {"titulo": 32},
        "listas": {"itens": (2, 4, 32)},
        "composicoes": ("cartoes", "um_por_vez"),
        "formato": '{"tipo": "lista", "fala": "...", "titulo": "até 32", "itens": [{"texto": '
        '"até 32", "quando": "palavra da fala"}], "composicao": "cartoes|um_por_vez"} (2 a 4)',
    },
    "numero": {
        "textos": {"valor": 10, "rotulo": 60, "fonte": 60},
        "obrigatorios": ("valor", "rotulo", "fonte"),
        "composicoes": ("anel", "gigante"),
        "formato": '{"tipo": "numero", "fala": "...", "valor": "87%", "rotulo": "o que o número '
        'diz (até 60)", "fonte": "de onde veio", "composicao": "anel|gigante"} (só com um '
        "número do material, com a fonte)",
    },
    # --- as cenas de arte (ADR 0110): a ideia em ícones e movimento, a fala na legenda ---
    "icone": {
        "textos": {"rotulo": 22, "quando": 30},
        "icones": ("icone",),
        "composicoes": ("heroi",),
        "formato": '{"tipo": "icone", "fala": "...", "icone": "<objeto>", "rotulo": '
        '"opcional, 1 a 3 palavras", "quando": "a palavra da fala em que ele se desenha"} (um '
        "conceito: o ícone enorme se desenha, ondas e faíscas saem dele)",
    },
    # --- a foto (ADR 0112): uma das fotos da marca ou uma foto livre (Wikimedia), com crédito ---
    "foto": {
        "textos": {"foto": 80, "rotulo": 26, "quando": 30},
        "icones": ("icone",),
        "composicoes": ("cheia", "polaroid", "janela"),
        "formato": '{"tipo": "foto", "fala": "...", "foto": "<nome de uma foto da marca> ou '
        'busca: <o que mostrar, em inglês>", "composicao": "cheia | polaroid | janela", '
        '"rotulo": "opcional, 1 a 3 palavras", "icone": "<objeto> (só na janela: o ícone que '
        'salta no canto da foto)", "quando": "palavra da fala"} (o real: "cheia" ocupa a tela, '
        '"polaroid" cai como uma foto impressa, "janela" é a foto com um ícone que comenta)',
    },
    # --- a lista (ADR 0114): um cartão que fica e troca de conteúdo, com o placar embaixo ---
    "item": {
        "textos": {
            "nome": 28,
            "detalhe": 80,
            "valor": 14,
            "categoria": 22,
            "quando": 30,
            "mostrar": 80,
        },
        "icones": ("icone",),
        "composicoes": ("cartao",),
        "formato": '{"tipo": "item", "fala": "...", "nome": "o nome do item, até 28", '
        '"detalhe": "o que ele faz, uma linha", "valor": "opcional, um número curto do material '
        '("24h", "3x")", "categoria": "opcional, até 22", "icone": "<objeto>", "mostrar": '
        '"opcional: logo: <marca> ou busca: <foto>, a imagem do item"} (um item de '
        "uma lista: itens seguidos ficam no mesmo cartão, que só troca o conteúdo, e um placar "
        "embaixo acende um selo por item; use de 3 a 8 seguidos, um por cena)",
    },
    "conexao": {
        "nos": (2, 4, 16),
        "composicoes": ("fluxo",),
        "formato": '{"tipo": "conexao", "fala": "...", "nos": [{"icone": "<objeto> ou '
        'logo: <ferramenta>", '
        '"rotulo": "1 ou 2 palavras", "quando": "palavra da fala"}]} (2 a 4: um fluxo ou uma '
        "integração; linhas ligam os nós e dados correm por elas)",
    },
    "hub": {
        "nos": (3, 6, 16),
        "campo_nos": "ao_redor",
        "composicoes": ("orbita",),
        "formato": '{"tipo": "hub", "fala": "...", "centro": {"icone": "<objeto> ou marca", '
        '"rotulo": "opcional"}, "ao_redor": [{"icone": "<objeto> ou logo: <ferramenta>", '
        '"rotulo": "opcional, 1 palavra", "quando": "palavra da fala"}]} (3 a 6 em volta de '
        "um centro: tudo ligado a "
        'uma coisa só; a marca no centro com "marca")',
    },
    # --- a copy manda (ADR 0115): cada coisa dita vira imagem real, na palavra ---
    "visual": {
        "batidas": (1, 4, 18),
        "composicoes": ("sequencia", "colagem"),
        "formato": '{"tipo": "visual", "fala": "...", "composicao": "sequencia|colagem", '
        '"batidas": [{"quando": "a palavra da fala", "mostrar": "logo: <marca> | busca: <2 ou 3 '
        'palavras em inglês> | <nome de uma foto da marca>", "rotulo": "opcional, até 18"}]} (1 a '
        '4 batidas: cada coisa concreta da fala aparece na palavra em que é dita; "sequencia" '
        'troca a imagem inteira a cada batida, em corte seco; "colagem" junta as imagens na '
        "tela, uma a uma)",
    },
    "fecho": {
        "textos": {"chamada": 32, "detalhe": 32, "palavra": 16},
        "obrigatorios": ("chamada",),
        "composicoes": ("marca", "chamada", "comenta"),
        "formato": '{"tipo": "fecho", "fala": "...", "chamada": "o convite, até 32", '
        '"detalhe": "opcional (por exemplo, Link na bio)", "composicao": "marca|chamada|comenta"} '
        '("marca" é o logo em 3D girando; "chamada" é o convite enorme na cor da marca, com uma '
        'seta para o link; "comenta" pede um comentário com uma palavra ("palavra": "VÍDEO", e a '
        'fala diz "comenta vídeo que eu te mando..."); alterne entre os vídeos)',
    },
}
for _regra in TIPOS.values():
    _regra.setdefault("obrigatorios", tuple(_regra.get("listas", {})) or ())
DE_ARTE = ("icone", "conexao", "hub", "foto", "visual")
DE_CARTAO = ("passos", "lista", "antes_depois", "conversa")

PROMPT = """Você é o diretor de criação de um Reels (vídeo vertical, cerca de {duracao} segundos)
para {marca}. Pense como roteirista, motion designer e editor: o vídeo precisa parecer feito por
uma equipe de audiovisual, nunca uma apresentação de slides.

{pedido}

Primeiro decida o objetivo (o que quem assiste deve pensar ou fazer no fim) e o público. Depois
escreva a fala do vídeo inteiro e divida em cenas; cada cena tem um papel só (prender, explicar,
provar, convidar) e um jeito de mostrar.

Responda só com JSON, sem texto em volta:
{{"objetivo": "...", "publico": "...", "formato": "...", "ganchos": ["...", "...", "...",
"...", "..."], "palavra": "...", "entrega": "...", "titulo": "...",
"capa": {{"texto": "...", "destaque": "...", "icone": "...", "foto": "..."}},
"legenda": "...",
"processo": "...", "assunto": "...",
"cenas": [{{"tipo": "...", "fala": "...", "pausa": "", "camera": "...", "transicao": "...",
...}}]}}

O limite mais importante: **a fala inteira tem de {minimo_palavras} a {total} palavras**. Conte
antes de responder; passou, corte. Um bom Reels diz pouco e mostra muito.

Regras:
- De {minimo} a {maximo} cenas. A primeira prende (veja Formato e gancho); a última é um
  "fecho".
- **Ritmo de edição:** um corte a cada 2 a 4 segundos. Uma ideia por cena; quando a ideia é
  grande, quebre em duas cenas seguidas com um "corte" entre elas. Vídeo lento parece pronto.
- fala: português do Brasil falado, uma frase curta e completa, até {fala} palavras. Sem
  siglas difíceis de falar e sem emojis. Números como se fala ("treze de novembro").
- pausa: "longa" na cena depois da qual quem escuta precisa de um segundo para absorver (o
  gancho, a conta, a virada); vazio nas outras. No máximo três "longa" no vídeo.
- **A tela não repete a fala.** Em "gancho" e "frase" a própria fala aparece animada; não escreva
  outro texto. Nas outras cenas, a legenda já mostra a fala: a tela mostra só a ideia, em poucas
  palavras (títulos e itens curtos, diferentes da fala).
- quando: a palavra da fala daquela cena (exatamente como escrita nela) em que o elemento entra;
  assim a tela acompanha a voz. Use palavras diferentes para elementos diferentes.
- camera: {cameras}. "empurra" é um soco de câmera na palavra de destaque (dê um destaque à
  cena); "afasta" e "desliza" mexem só na chegada; "parado" não mexe.
- transicao (como a cena entra): {transicoes}. "mascara" abre um círculo a partir do que estava
  em foco; "deslize" é um chicote rápido para o lado; "zoom" atravessa o que estava em foco; "cor"
  inunda a tela com a cor da marca (para mudar de assunto); "corte" é seco, na batida. As cenas são
  cartas inteiras: "carta" vira a tela como carta de baralho (virada, revelação, antes e depois);
  "baralho" joga a carta de cima para o lado e revela a próxima (o próximo item, o próximo passo);
  "cubo" gira a tela como um cubo (outro lado, outra etapa); "fatias" faz a cena nova descer em
  tiras (revelação forte). Use 4 a 6 tipos no vídeo, pelo menos dois desses de carta, e nunca a
  mesma transição em cenas seguidas; "corte" nos momentos de impacto.
- fundo: {fundos}. **Paleta estável:** a maior parte das cenas no mesmo fundo (o padrão ou
  "claro"); a tela inteira na cor ("cor", ou a frase "cheia") no máximo uma vez, no momento-chave.
- **A copy é a mãe da animação.** Escreva a fala primeiro; depois faça cada coisa concreta que
  ela diz aparecer na tela na palavra em que é dita: "prédio" vira a foto de um prédio,
  "WhatsApp" vira o logo do WhatsApp, "Pix" vira o logo do Pix. A maior parte
  das cenas é "visual" (as batidas) ou "foto"; "item" com imagem no máximo duas vezes. Use
  logos de empresas que existem ("logo: whatsapp", "logo: google calendar", "logo: ifood",
  "logo: instagram") e fotos ("busca: office building"). Nada de ícone gigante sozinho na
  tela: o conceito vira a coisa real em foto; o fluxo vira "conexao" ou "hub". Cartões de
  texto (passos, lista, antes_depois, conversa) no máximo um no vídeo.
- Varie os tipos e as composições. No máximo um "frase" seguido de outro tipo de texto.
- **Nada de passo a passo.** Não conte em voz alta ("primeiro", "segundo", "passo um", "são
  três coisas") nem numere na tela: o vídeo é uma história com tensão e virada, não um tutorial.
  Cenas que enumeram (item, passos, lista) no máximo duas no vídeo.
- Não invente dado, cliente real nem depoimento. A história de exemplo se apresenta como
  exemplo ("pensa na", "imagina"), com números de exemplo que a conta deixa claros ("se ela perde
  três clientes por semana, de cento e cinquenta reais cada..."); nunca diga que aconteceu de
  verdade nem que é cliente de quem fala. "numero" com dado real só com a fonte do material; com
  a conta do exemplo, a fonte é "conta de exemplo". Uma "conversa" é sempre um exemplo.
- capa: a capa do Reels, uma peça à parte do vídeo, sobre o tema (é o que forma o perfil).
  texto: o tema como título de capa, de 2 a 5 palavras, forte e específico ("Cobrança no
  automático", "Agenda que se enche sozinha", "Orçamento em 10 minutos"), nunca genérico
  ("Automação para empresas"); destaque: 1 ou 2 palavras do texto, em cor; icone: o objeto do
  tema, em inglês ("receipt", "calendar", "wrench"); foto: o nome exato de uma foto da marca em
  que aparece quem fala (um retrato), ou vazio se não houver.
- titulo: até 60 caracteres. legenda: a do Instagram, de 300 a 1.000 caracteres, com o gancho, a
  explicação em parágrafos curtos, a chamada, no máximo 3 emojis e até 5 hashtags no fim.
{tom}
## A fala (alguém fala, alguém escuta)
O vídeo é narrado: uma pessoa fala e outra escuta, muitas vezes sem olhar a tela. Escreva para o
ouvido, não para a legenda.
- Leia todas as falas em sequência, como um texto só, antes de responder: tem de soar como
  alguém contando uma história a outra pessoa, com começo, meio e fim, sem pular um passo. Quem
  só escuta entende tudo.
- Cada fala é gravada sozinha, então é uma frase completa, com sujeito e verbo. Nunca corte uma
  frase entre duas cenas.
- Ligue as cenas com o conectivo falado: "só que", "aí", "e o pior", "agora faz a conta", "sabe
  o que a gente faria?", "o resultado?", "e não é só", "por isso". A passagem de uma parte para
  a outra (do problema para a conta, da conta para a solução, da solução para a ponte) é dita,
  não só mostrada.
- Diga quem faz o quê: o nome e o que a pessoa é ("a Renata, dona de uma agência de viagens");
  com duas pessoas na história (a dona e o cliente), nada de "ele" ou "ela" solto: "o cliente".
- Português falado, natural, nada de telegrama: com artigos e preposições ("ela monta a
  proposta no Word", não "proposta na mão, no Word"). Sem dois-pontos, barras, parênteses,
  siglas nem listas na fala; números como se falam ("dois mil reais", "dez minutos").
- A pontuação é a respiração da voz: vírgula para a pausa curta, ponto no fim da ideia, ponto
  de interrogação na pergunta que puxa a próxima cena; reticências só no suspense, uma vez.
{formatos}
{entrega}
Tipos de cena:
{tipos}

Ícones: escreva em inglês o objeto concreto que a fala diz, como "pizza", "stethoscope",
"delivery truck", "tooth", "dumbbell", "scissors", "shopping cart", "calendar" (o Zé tem 1.500
desenhos e acha o mais parecido). Prefira o objeto do assunto ao símbolo genérico: para uma
pizzaria, "pizza", não "store"; para uma clínica, "stethoscope", não "heart".
{fotos}{recentes}
## Linha editorial (o manual do site)
{manual}
"""


class RoteiroErro(ValueError):
    """O plano não veio no formato; a mensagem vai para a tela (e para o modelo, na volta)."""


@dataclass
class Roteiro:
    titulo: str
    legenda: str
    cenas: list[dict[str, Any]] = field(default_factory=list)
    objetivo: str = ""
    publico: str = ""
    formato: str = ""
    palavra: str = ""  # a palavra para comentar (ADR 0116)
    entrega: str = ""  # o que quem comenta recebe no direct
    capa: str = ""  # o texto da capa do Reels (ADR 0123): o tema
    ganchos: list[str] = field(default_factory=list)  # os candidatos que o diretor escreveu
    capa_destaque: str = ""
    capa_icone: str = ""  # o objeto do tema, para o ícone da capa
    capa_foto: str = ""  # uma foto da marca com quem fala (o retrato)
    processo: str = ""  # a chave em formatos.PROCESSOS (a trava de temas, ADR 0125)
    assunto: str = ""  # o assunto em poucas palavras

    @property
    def falas(self) -> list[str]:
        return [str(c["fala"]) for c in self.cenas]

    def para_json(self) -> dict[str, Any]:
        return {
            "objetivo": self.objetivo,
            "formato": self.formato,
            "palavra": self.palavra,
            "entrega": self.entrega,
            "publico": self.publico,
            "titulo": self.titulo,
            "processo": self.processo,
            "assunto": self.assunto,
            "capa": {
                "texto": self.capa,
                "destaque": self.capa_destaque,
                "icone": self.capa_icone,
                "foto": self.capa_foto,
            },
            "ganchos": self.ganchos,
            "legenda": self.legenda,
            "cenas": self.cenas,
        }


def base(palavra: str) -> str:
    """A palavra sem acento, pontuação nem maiúscula: para casar o "quando" com a fala."""
    sem_acento = unicodedata.normalize("NFKD", palavra).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def _texto(valor: Any, limite: int) -> str:
    texto = " ".join(str(valor or "").split())
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def limites(duracao: int) -> tuple[int, int, int, int]:
    """(mínimo e máximo de cenas, mínimo e máximo de palavras da fala) para a duração."""
    minimo, maximo = DURACOES.get(duracao, DURACOES[DURACAO_PADRAO])
    total = round((duracao - LONGAS * PAUSA_LONGA_S) * PALAVRAS_POR_SEGUNDO)
    return minimo, maximo, round(total * 0.6), total


def tipos_do_estilo(estilo: Estilo) -> dict[str, str]:
    """O formato de cada tipo de cena para o modelo: os embutidos e os que o estilo acrescenta."""
    extras = {t: f if t in f else f"{t}: {f}" for t, f in estilo.cenas_extras.items()}
    # o ícone gigante sozinho na tela saiu do cardápio (ADR 0125): a coisa real, em foto
    return {**{t: d["formato"] for t, d in TIPOS.items() if t != "icone"}, **extras}


def receita(cenas: list[dict[str, Any]]) -> str:
    """O esqueleto de um vídeo: tipo, transição e fundo de cada cena, em ordem."""
    return " → ".join(
        f"{c.get('tipo')} ({c.get('composicao')}, {c.get('transicao')}, {c.get('fundo', 'escuro')})"
        for c in cenas
    )


def miolo(cenas: list[dict[str, Any]]) -> tuple[str, ...]:
    """Os tipos entre o gancho e o fecho: o que faz dois vídeos parecerem o mesmo."""
    return tuple(str(c.get("tipo")) for c in cenas[1:-1])


def secao_recentes(recentes: list[dict[str, Any]]) -> str:
    """A memória dos últimos vídeos para o diretor: o tema, o gancho e a receita de cada um,
    com o pedido de fazer diferente (sem isso, o modelo repete a receita que deu certo)."""
    if not recentes:
        return ""
    linhas = []
    for r in recentes:
        cenas = r.get("cenas") or []
        gancho = cenas[0].get("fala", "") if cenas else ""
        formato = r.get("formato") or "livre"
        linhas.append(
            f'- "{r.get("titulo", "")}" · formato: {formato} · gancho: "{gancho}" · '
            f"{receita(cenas)}"
        )
    return (
        "\n## Os últimos vídeos desta marca (não repita a receita)\n"
        + "\n".join(linhas)
        + "\nFaça este diferente de todos eles: outro formato, outra sequência de tipos, um "
        "gancho que abre de outro jeito (pergunta, número, cena, provocação), transições e fundos "
        "em outra ordem e analogias novas. Não repita um tema já tratado.\n"
    )


def secao_fotos(fotos: list[str]) -> str:
    """As imagens que o diretor pode pedir: as fotos da marca pelo nome, a foto livre e o logo."""
    da_marca = (
        "Fotos da marca (o nome exato; são as mais fortes, é o real de quem fala): "
        + ", ".join(fotos[:40])
        if fotos
        else "A marca ainda não tem fotos próprias."
    )
    return (
        f'\n## Imagens (o que "mostrar" aceita)\n{da_marca}\n'
        '- "logo: <marca>": o logo de uma empresa que existe, na cor dela ("logo: whatsapp", '
        '"logo: ifood", "logo: mercado pago"). Só marcas que a fala cita de verdade.\n'
        '- "busca: <2 ou 3 palavras concretas em inglês>": uma foto livre de uma coisa ou um lugar '
        '("busca: office building", "busca: mechanic workshop"); nunca uma pessoa. Seja '
        'específico: "car dashboard", não "car interior" (que traz vagão de trem).\n'
        '- "site: <endereço>": o print do site de uma ferramenta, numa janela de navegador ("site: '
        'n8n.io"); até 3 por vídeo, só de sites de verdade que a fala cita.\n'
        'Até 12 imagens livres por vídeo. A cena "foto" mostra uma imagem grande sozinha; a '
        '"visual" mostra várias, cada uma na sua palavra.\n'
    )


def montar_prompt(
    marca: str,
    pedido: str,
    manual: str,
    estilo: Estilo,
    duracao: int = DURACAO_PADRAO,
    recentes: list[dict[str, Any]] | None = None,
    fotos: list[str] | None = None,
    linha: str = "",
    entrega: str = "",
    palavra: str = "",
) -> str:
    minimo, maximo, minimo_palavras, total = limites(duracao)
    return PROMPT.format(
        duracao=duracao,
        marca=marca or "uma empresa",
        pedido=pedido,
        minimo=minimo,
        maximo=maximo,
        minimo_palavras=minimo_palavras,
        total=total,
        fala=FALA_PALAVRAS,
        cameras=" | ".join(CAMERAS),
        transicoes=" | ".join(TRANSICOES),
        fundos=" | ".join(FUNDOS),
        tom=f"- Tom: {estilo.tom}\n" if estilo.tom else "",
        tipos="\n".join(f"- {formato}" for formato in tipos_do_estilo(estilo).values()),
        manual=manual or "(o site não tem manual; use um tom profissional, claro e direto)",
        recentes=secao_recentes(recentes or []),
        formatos=formatos.secao(),
        entrega=formatos.secao_entrega(linha, entrega, palavra),
        fotos=secao_fotos(fotos or []),
    )


def _icone(nome: Any) -> str:
    """O ícone da biblioteca para o objeto pedido (nunca um desenho do modelo)."""
    return biblioteca.achar(str(nome or "").strip()[:60])


def _sem_icone(bruta: Any, abertura: bool) -> Any:
    """O ícone gigante sozinho na tela vira a coisa real em foto (ADR 0125): na abertura, a foto
    cheia; no meio, uma batida da cena visual. Sem foto que sirva, vira a frase na tela."""
    if not isinstance(bruta, dict) or bruta.get("tipo") != "icone":
        return bruta
    objeto = _texto(bruta.get("icone"), 40) or _texto(bruta.get("rotulo"), 40) or "idea"
    base_ = {k: bruta[k] for k in ("fala", "pausa", "camera", "transicao", "fundo") if k in bruta}
    if abertura:
        return {**base_, "tipo": "foto", "composicao": "cheia", "foto": f"busca: {objeto}"}
    batida = {"quando": bruta.get("quando", ""), "mostrar": f"busca: {objeto}",
              "rotulo": bruta.get("rotulo", "")}  # fmt: skip
    return {**base_, "tipo": "visual", "composicao": "sequencia", "batidas": [batida]}


def _no(x: dict[str, Any], limite: int, fala: str) -> dict[str, Any]:
    """Um nó do fluxo: o ícone do objeto ou o logo da ferramenta ("logo: whatsapp"; o ícone
    fica de reserva, se o logo não vier)."""
    pedido = str(x.get("icone") or "").strip()
    logo = pedido.lower().startswith("logo:")
    no = {
        "icone": _icone(pedido[5:] if logo else pedido),
        "rotulo": _texto(x.get("rotulo"), limite),
        "quando": _quando(x.get("quando"), fala),
    }
    if logo:
        no["mostrar"] = _texto(pedido, 60)
    return no


def icones_usados(cenas: list[dict[str, Any]]) -> set[str]:
    nomes: set[str] = set()
    for c in cenas:
        if isinstance(c.get("icone"), str):
            nomes.add(c["icone"])
        for campo in ("nos", "ao_redor", "batidas"):
            nomes.update(str(x.get("icone", "")) for x in c.get(campo) or [])
        if isinstance(c.get("centro"), dict):
            nomes.add(str(c["centro"].get("icone", "")))
        nomes.update(str(x) for x in c.get("icones") or [])
    return {n for n in nomes if n in biblioteca.todos()}


def _quando(valor: Any, fala: str) -> str:
    """O "quando" só vale se a palavra está na fala da cena."""
    partes = str(valor or "").split()
    alvo = base(partes[0]) if partes else ""
    return alvo if alvo and any(base(p) == alvo for p in fala.split()) else ""


def _itens(bruta: Any, limite: int, fala: str) -> list[dict[str, str]]:
    """Uma lista de itens, como texto ou como {"texto", "quando"}."""
    saida = []
    for x in bruta if isinstance(bruta, list) else []:
        if isinstance(x, dict):
            texto, quando = _texto(x.get("texto"), limite), _quando(x.get("quando"), fala)
        elif isinstance(x, str):
            texto, quando = _texto(x, limite), ""
        else:
            continue
        if texto:
            saida.append({"texto": texto, "quando": quando})
    return saida


def _cena(bruta: Any, extras: dict[str, str]) -> dict[str, Any]:
    if not isinstance(bruta, dict):
        raise RoteiroErro("Uma cena veio fora do formato.")
    tipo = str(bruta.get("tipo", ""))
    fala = _texto(bruta.get("fala"), 200)
    if not fala:
        raise RoteiroErro("Uma cena veio sem fala.")
    if len(fala.split()) > FALA_PALAVRAS + 8:
        raise RoteiroErro(f"Uma fala ficou longa demais (até {FALA_PALAVRAS} palavras).")
    camera = str(bruta.get("camera", ""))
    transicao = str(bruta.get("transicao", ""))
    if fala[-1] not in ".!?…":
        fala += "."  # gravada sozinha, a frase fecha (sem o ponto, a voz fica no ar)
    comum = {
        "tipo": tipo,
        "fala": fala,
        "pausa": "longa" if bruta.get("pausa") == "longa" else "",
        "camera": camera if camera in CAMERAS else "empurra",
        "transicao": transicao if transicao in TRANSICOES else "zoom",
        "fundo": str(bruta.get("fundo")) if bruta.get("fundo") in FUNDOS else "escuro",
    }
    if tipo in extras and tipo not in TIPOS:
        # uma cena do estilo: só texto e listas de texto, cortados
        cena: dict[str, Any] = dict(comum)
        for k, v in bruta.items():
            if k in cena or not re.fullmatch(r"[a-z_]{1,24}", str(k)):
                continue
            if isinstance(v, list):
                cena[k] = [_texto(x, 120) for x in v[:6] if isinstance(x, (str, int, float))]
            elif isinstance(v, (str, int, float)):
                cena[k] = _texto(v, 200)
        return cena
    regra = TIPOS.get(tipo)
    if regra is None:
        raise RoteiroErro(f"Tipo de cena desconhecido: {tipo or 'vazio'}.")
    cena = dict(comum)
    composicao = str(bruta.get("composicao", ""))
    composicoes = regra["composicoes"]
    cena["composicao"] = composicao if composicao in composicoes else composicoes[0]
    if cena["composicao"] == "gigante" and tipo == "gancho" and len(fala.split()) > 7:
        cena["composicao"] = "centro"  # uma palavra por linha só cabe com fala curta
    if cena["composicao"] == "cortes" and len(fala.split()) > CORTES_PALAVRAS:
        cena["composicao"] = "carimbo"  # uma palavra por tela, só com fala curta
    for campo, limite in regra.get("textos", {}).items():
        if valor := _texto(bruta.get(campo), limite):
            cena[campo] = valor
    if "quando" in cena:
        cena["quando"] = _quando(cena["quando"], fala)
    if tipo == "foto" and not cena.get("foto"):
        raise RoteiroErro("A cena foto precisa da foto (o nome de uma foto da marca ou a busca).")
    for campo, (minimo, maximo, limite) in regra.get("listas", {}).items():
        itens = _itens(bruta.get(campo), limite, fala)[:maximo]
        if len(itens) < minimo:
            raise RoteiroErro(f"A cena {tipo} precisa de pelo menos {minimo} itens.")
        cena[campo] = itens
    if "mensagens" in regra:
        minimo, maximo, limite = regra["mensagens"]
        msgs = [
            {
                "de": "cliente" if m.get("de") == "cliente" else "empresa",
                "texto": _texto(m.get("texto"), limite),
                "quando": _quando(m.get("quando"), fala),
            }
            for m in (bruta.get("mensagens") or [])
            if isinstance(m, dict) and str(m.get("texto", "")).strip()
        ][:maximo]
        if len(msgs) < minimo:
            raise RoteiroErro("A conversa precisa de pelo menos 2 mensagens.")
        cena["mensagens"] = msgs
    if "icones" in regra:
        cena["icone"] = _icone(bruta.get("icone"))
    if "nos" in regra:
        minimo, maximo, limite = regra["nos"]
        campo = regra.get("campo_nos", "nos")
        nos = [_no(x, limite, fala) for x in (bruta.get(campo) or []) if isinstance(x, dict)][
            :maximo
        ]
        if len(nos) < minimo:
            raise RoteiroErro(f"A cena {tipo} precisa de pelo menos {minimo} nós.")
        cena[campo] = nos
        if tipo == "hub":
            centro: dict[str, Any] = (
                bruta["centro"] if isinstance(bruta.get("centro"), dict) else {}
            )
            marca = str(centro.get("icone", "")) == "marca"
            cena["centro"] = {
                "icone": "marca" if marca else _icone(centro.get("icone")),
                "rotulo": _texto(centro.get("rotulo"), limite),
            }
    if "batidas" in regra:
        minimo, maximo, limite = regra["batidas"]
        batidas = [
            {
                "quando": _quando(b.get("quando"), fala),
                "mostrar": _texto(b.get("mostrar"), 80),
                "rotulo": _texto(b.get("rotulo"), limite),
            }
            for b in (bruta.get("batidas") or [])
            if isinstance(b, dict) and str(b.get("mostrar", "")).strip()
        ][:maximo]
        if len(batidas) < minimo:
            raise RoteiroErro("A cena visual precisa de pelo menos uma batida (o que mostrar).")
        cena["batidas"] = batidas
    if tipo == "numero" and not re.search(r"\d", cena.get("valor", "")):
        raise RoteiroErro("O número da cena não tem número.")
    faltando = [c for c in regra["obrigatorios"] if not cena.get(c)]
    if faltando:
        raise RoteiroErro(f"A cena {tipo} veio sem {', '.join(faltando)}.")
    if tipo == "antes_depois" and not (cena.get("antes") and cena.get("depois")):
        raise RoteiroErro("A cena antes_depois veio sem o antes ou o depois.")
    return cena


def interpretar(resposta: str, estilo: Estilo, duracao: int = DURACAO_PADRAO) -> Roteiro:
    """O JSON do modelo, conferido. Aceita o JSON cercado por texto ou bloco de código."""
    minimo, maximo, _, total = limites(duracao)
    achado = re.search(r"\{.*\}", resposta, re.S)
    if not achado:
        raise RoteiroErro("O modelo não devolveu um roteiro.")
    try:
        dados = json.loads(achado.group(0))
    except ValueError as erro:
        raise RoteiroErro("O roteiro veio com JSON inválido.") from erro
    brutas = dados.get("cenas") if isinstance(dados, dict) else None
    if not isinstance(brutas, list) or not minimo <= len(brutas) <= maximo:
        raise RoteiroErro(f"O roteiro precisa de {minimo} a {maximo} cenas.")
    cenas = [_cena(_sem_icone(c, i == 0), estilo.cenas_extras) for i, c in enumerate(brutas)]

    # a paleta estável: a tela inteira na cor da marca no máximo uma vez fora do fecho
    # (a frase "cheia" é a tela na cor; a foto "cheia" é a foto, não conta)
    def na_cor(c: dict[str, Any]) -> bool:
        return c["fundo"] == "cor" or (c["tipo"] == "frase" and c.get("composicao") == "cheia")

    for c in [c for c in cenas[:-1] if na_cor(c)][1:]:
        c["fundo"] = "claro" if c["fundo"] == "cor" else c["fundo"]
        if c["tipo"] == "frase" and c.get("composicao") == "cheia":
            c["composicao"] = "centro"
    for antes, cena in itertools.pairwise(cenas):
        if antes["tipo"] == cena["tipo"] == "item":
            # itens seguidos são o mesmo cartão: o mesmo fundo, sem transição
            cena["fundo"], cena["transicao"] = antes["fundo"], "corte"
    # a abertura mostra a imagem no primeiro instante: um ícone que só entra na terceira palavra
    # deixa o gancho começar com a tela vazia
    cenas[0].pop("quando", None)
    if cenas[0]["tipo"] not in ABERTURAS or cenas[-1]["tipo"] != "fecho":
        raise RoteiroErro(
            f"O roteiro precisa abrir com {', '.join(ABERTURAS)} e terminar com um fecho."
        )
    if dados.get("formato") == "caso" and not any(c["tipo"] in FLUXOS for c in cenas):
        raise RoteiroErro(
            'No formato "caso", a solução é um fluxo animado: use uma cena "conexao" ou "hub", '
            "com os logos das ferramentas."
        )
    enumeradas = sum(c["tipo"] in ENUMERADOS for c in cenas)
    if enumeradas > MAXIMO_ENUMERADOS:
        raise RoteiroErro(
            f"O roteiro virou lista ({enumeradas} cenas de item, passos ou lista; até "
            f"{MAXIMO_ENUMERADOS}). Conte uma história com virada, não um passo a passo."
        )
    palavras = sum(len(c["fala"].split()) for c in cenas)
    if palavras > total + 10:
        raise RoteiroErro(
            f"A fala ficou longa demais para {duracao} s ({palavras} palavras; até {total}). "
            f"Corte {palavras - total} palavras ou mais: frases mais curtas e, se precisar, uma "
            "cena a menos."
        )
    # o fecho é sempre o "comenta" (a entrega é o motivo de comentar)
    fecho = cenas[-1]
    palavra = _texto(fecho.get("palavra") or dados.get("palavra"), 16)
    palavra = palavra or _texto((str(fecho.get("chamada", "")).split() or ["comenta"])[0], 16)
    fecho.update(composicao="comenta", palavra=palavra)
    titulo = _texto(dados.get("titulo"), 60) or _texto(cenas[0]["fala"], 60)
    capa = (
        dados.get("capa") if isinstance(dados.get("capa"), dict) else {"texto": dados.get("capa")}
    )
    return Roteiro(
        titulo,
        str(dados.get("legenda") or "").strip()[:LIMITE_LEGENDA],
        cenas,
        _texto(dados.get("objetivo"), 200),
        _texto(dados.get("publico"), 200),
        formato if (formato := str(dados.get("formato", ""))) in formatos.FORMATOS else "",
        palavra.upper(),
        _texto(dados.get("entrega"), 140),
        _texto(capa.get("texto"), 60),
        [_texto(g, 120) for g in (dados.get("ganchos") or [])[:8] if isinstance(g, str)],
        _texto(capa.get("destaque"), 30),
        _texto(capa.get("icone"), 40),
        _texto(capa.get("foto"), 80),
        processo if (processo := str(dados.get("processo", ""))) in formatos.PROCESSOS else "",
        _texto(dados.get("assunto"), 80),
    )


def tempos_dos_gatilhos(cena: dict[str, Any], palavras: list[dict[str, Any]]) -> dict[str, Any]:
    """Os "quando" da cena em segundos desde o começo dela (`tempos_<lista>` e `tempo`, do depois),
    pelo tempo real das palavras. O que não tem "quando" fica None: a página distribui no tempo
    da cena."""
    inicio = float(cena["inicio"])

    def achar(alvo: str) -> float | None:
        if not alvo:
            return None
        for p in palavras:
            if base(str(p["p"])) == alvo:
                return round(max(0.0, float(p["i"]) - inicio), 3)
        return None

    saida: dict[str, Any] = {}
    for campo in ("passos", "itens", "mensagens", "nos", "ao_redor", "batidas"):
        if campo in cena:
            saida[f"tempos_{campo}"] = [achar(str(x.get("quando", ""))) for x in cena[campo]]
    if cena.get("quando"):
        saida["tempo"] = achar(str(cena["quando"]))
    return saida
