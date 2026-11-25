# 0138 — Visuais no chat: apresentações, diagramas e painéis animados, com parâmetros

- Data: 25/11/2026
- Status: **Aceito** (desenho aprovado em imagens; MVP).
- Segue os ADRs 0136 (o Início é a conversa) e 0137 (anexos no chat).

## Contexto

Pedido de quem usa: o Zé criar no chat o que o Claude chama de visuais personalizados e artefatos
(o mercado diz *generative UI*): apresentações, diagramas e painéis em HTML, animados, com
parâmetros para mexer na hora (volumes, combinações, cartões de imagem), para ver em tela cheia e
baixar. Pedido de imagem realista é outra peça (geração de imagem), que vem depois.

## Decisão

1. **A ferramenta `visual_criar`** (título, espécie, HTML): o cérebro escreve só o conteúdo do
   `<body>`, com as peças do **kit do Zé** (`zervis/visuais/kit.css` e `kit.js`): slides, cartões,
   cartões de imagem, números que contam, barras, anel, fluxo animado, lista e linha do tempo, e
   controles (`data-param`) que viram variável CSS, texto e contas (`data-calc`) na hora. O kit dá
   a fonte do painel, o fundo, as animações e a impressão; o visual fica bonito sem o modelo
   desenhar o estilo do zero. Imagem anexada no chat entra num cartão por `zk:anexo/<nome>`.
2. **A guarda** (`DADOS/visuais/<id>.html` e `.json`, 0600, 90 dias). A página inteira se monta
   ao servir, então o kit novo vale para os antigos.
3. **Isolamento** (falhar fechado): `/fluxo/visual` vai com regra própria (CSP): sem rede, sem
   formulário, numa origem à parte (`sandbox allow-scripts`) e só dentro do painel; a moldura do
   chat também é `sandbox="allow-scripts"`. O HTML é do modelo, que pode ter lido uma página de
   fora: ele não alcança o painel, o token nem a internet. Por isso a ferramenta passa sem
   perguntar, também num turno "de fora".
4. **No chat:** o visual entra no fio do dia no momento em que foi criado, como cartão com o
   título, a moldura, a tela cheia e o baixar (HTML interativo; PNG e PDF pelo Chromium sem tela,
   o PDF com um slide por página). O fio passa a mudar só as falas que mudaram: redesenhar a
   moldura a cada mensagem faria a apresentação recomeçar.
5. Pedidos de apresentação, slides, diagrama, gráfico, visual ou infográfico vão ao cérebro
   completo (a via rápida não tem ferramentas).

## Consequências

- O kit cresce com o uso: peça nova (mapa, tabela comparativa, linha do tempo interativa) entra
  em `kit.css`/`kit.js` e no resumo da ferramenta.
- A geração de imagem realista (GPT Image, Nano Banana) é o próximo passo; a imagem gerada vai
  poder entrar num cartão do kit.
