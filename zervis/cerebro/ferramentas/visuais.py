"""Os visuais do chat (ADR 0138): o cérebro monta apresentações, diagramas, gráficos e painéis com
o kit do Zé, e o chat do Início os mostra. Só grava na pasta dos visuais e a página roda isolada
(sem rede, sem o painel), então passa sem perguntar."""

import asyncio
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.visuais import ESPECIES, Visuais, VisualErro

KIT = (
    "Escreva só o conteúdo do <body> (sem <html>, <head> nem links de fora: a página não tem "
    'internet; imagem só data: ou a de um anexo do chat, src="zk:anexo/<nome do anexo>"). '
    "O kit já dá a fonte, o fundo escuro com o ciano do Zé, as animações e a impressão. Peças: "
    'apresentação <div class="zk-slides"><section class="zk-slide">…</section>…</div> (passa '
    'no clique e nas setas; data-auto="5" passa sozinho); <div class="zk-pagina"> para uma '
    'página só; <div class="zk-grade"> (cartões lado a lado; style="--zk-min:240px"); '
    '<div class="zk-cartao" data-cor="violeta">; cartão de imagem <figure class="zk-cartao '
    'zk-imagem"><img src=…><figcaption>…</figcaption></figure>; <span class="zk-rotulo"> '
    '(linha pequena acima do título); <span class="zk-destaque"> (texto em gradiente); '
    '<span class="zk-chip">; <div class="zk-icone">⚡</div>; número que conta '
    '<b class="zk-numero" data-contar="1830" data-formato="R$ {v}">0</b>; barras <div '
    'class="zk-barras"><div class="zk-barra" style="--v:.7"><b>70</b><span>Seg</span></div>…'
    '</div>; anel <div class="zk-anel" style="--v:.72"><b>72%</b><span>meta</span></div>; '
    'fluxo <div class="zk-fluxo"><div class="zk-no"><span>📷</span>Câmera<small>…</small></div>'
    '<i class="zk-cabo"></i>…</div>; <ol class="zk-lista"> (itens numerados que entram em '
    'sequência); <div class="zk-tempo"> (linha do tempo); data-entra="1|2|3" (entra com '
    "atraso). Cores: data-cor=ciano|violeta|ambar|verde|rosa|azul|vermelho. Parâmetros que quem "
    'usa muda na hora: <div class="zk-controles"><label class="zk-controle">Volume <output '
    'data-mostra="volume" data-formato="{v} un"></output><input type="range" min="0" max="500" '
    'value="120" data-param="volume"></label></div>; o valor vira a variável CSS --volume (e '
    '--volume-n, de 0 a 1: style="--v: var(--volume-n)" numa barra), o texto de '
    '[data-mostra="volume"] e as contas <b data-calc="volume * preco" data-formato="R$ {v}">'
    '</b>; <div class="zk-alternar" data-param="plano"><button data-valor="1" '
    'aria-pressed="true">Mensal</button><button data-valor="12">Anual</button></div> escolhe '
    "entre combinações. Script próprio pode ouvir document.addEventListener('zk:param', …). "
    "Faça bonito e responsivo: cabe num cartão de ~800 x 380 px no chat, em tela cheia e no "
    "celular (340 px); textos curtos, poucos elementos por slide."
)


def ferramentas(visuais: Visuais | None) -> list[SdkMcpTool[Any]]:
    if visuais is None:
        return []

    @tool(
        "visual_criar",
        "Cria um visual no chat do Início: apresentação, diagrama, gráfico, painel com parâmetros "
        "ou página, em HTML animado, para ver em tela cheia e baixar (HTML, PNG ou PDF). Use "
        "quando pedirem para mostrar, apresentar, comparar, simular ou explicar com imagem, ou "
        "quando um visual explica melhor que a fala. Depois, diga em uma frase que está no chat; "
        "não leia o conteúdo. " + KIT,
        {
            "type": "object",
            "properties": {
                "titulo": {"type": "string", "description": "Auditoria da câmera iCSee"},
                "especie": {"type": "string", "enum": list(ESPECIES)},
                "html": {"type": "string", "description": "O conteúdo do <body>, com o kit."},
            },
            "required": ["titulo", "html"],
        },
    )
    async def visual_criar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            visual = await asyncio.to_thread(
                visuais.criar,
                str(args.get("titulo", "")),
                str(args.get("html", "")),
                str(args.get("especie", "apresentacao")),
            )
        except VisualErro as erro:
            return _erro(erro)
        return _texto({"criado": visual.titulo, "id": visual.id, "onde": "no chat do Início"})

    return [visual_criar]
