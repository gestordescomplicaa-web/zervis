# 0106 — Vídeos (Reels) em Marketing: o modelo escreve o roteiro, o Zé desenha

- Data: 18/11/2026
- Status: **Aceito** (pedido de quem usa, 18/11/2026).
- Etapa 1 do plano dos vídeos. Segue o [ADR 0093](0093-posts-do-instagram.md) (a marca do site)
  e o [ADR 0104](0104-aprovacao-no-painel.md) (publicar só com o "sim" no painel, na etapa 2).

## Contexto

Os dois vídeos de apresentação do Zé (`docs/video/`) mostraram que um Reels narrado, com a marca e
movimento de verdade, sai da própria máquina em cerca de 5 minutos: uma página que desenha cada
instante, o Chromium sem tela, uma trilha composta em código e o FFmpeg. O método veio da skill
[`brag`](https://github.com/latent-spaces/brag) (MIT); nenhum código dela foi copiado.

Quem usa quer o mesmo para o próprio negócio: Reels explicativos, com design de verdade, sobre
qualquer assunto, e sem prender ninguém a um fornecedor nem encher o Zé de dependências.

## Decisão

1. **O modelo escreve só o roteiro, num formato fechado** (`zervis/video/roteiro.py`): as cenas,
   o texto da tela e a fala de cada uma. Nunca HTML nem código. O Zé confere tudo (tipos, limites,
   começar com um gancho e terminar com um fecho, a narração de um Reels), corta o que passa e
   mostra o texto como texto. Um roteiro recusado volta uma vez ao modelo com o motivo.
2. **O Zé desenha com uma biblioteca própria de cenas** (`zervis/video/web/`): gancho, frase,
   passos, antes e depois, conversa (sempre com o selo "Ilustração"), lista, número (só com a
   fonte) e fecho. O motor (`motor.js`) é escrito aqui, sem GSAP nem biblioteca externa: cada
   quadro é função só do tempo, então a captura pode ser em paralelo. A legenda acende palavra
   por palavra, a onda segue a voz real e a música abaixa sob a fala.
3. **Estilos são pastas** (`zervis/video/estilos.py`): `estilo.json` (nome, fontes, andamento e
   energia da trilha, tom do texto, cenas novas para o modelo), `estilo.css` (o visual) e,
   opcional, `cenas.js` (cenas novas ou trocadas). O Zé traz o "Zérvis" como exemplo; os de quem
   usa ficam em `<config>/video/estilos/<pasta>/` e, com o mesmo nome, valem no lugar do embutido.
   As cores e as fontes vêm da marca do site, como nos posts.
4. **A voz é a do painel** (`narracao.py`): Fish Audio, ElevenLabs ou o Cadu local, de graça. Cada
   fala começa numa batida da música, e a cena abre junto com ela. Sem narração, o tempo vem do
   número de palavras.
5. **Nada novo para instalar:** Chromium (já dos posts), FFmpeg (já da câmera), numpy e websockets
   (já dependências). Onde faltar Chromium ou FFmpeg, a função aparece como indisponível.
6. **Em Marketing, um vídeo por vez, em segundo plano:** a etapa aparece no cartão, o Zé avisa
   quando fica pronto, e o vídeo fica como rascunho, com prévia, download, refazer com um ajuste e
   descartar. Os quadros são apagados no fim; ficam o MP4, a capa e o roteiro.

## Consequências

- Publicar no Instagram (Reels) é a etapa 2, com o mesmo caminho dos posts e a aprovação no
  painel. Pedir pela voz e pelo WhatsApp é a etapa 3.
- Um vídeo de 25 s leva cerca de 5 minutos e ocupa os núcleos da máquina enquanto desenha (metade
  deles, até 6). Na VPS sem GPU, mais.
- As fontes da marca vêm do Google Fonts no momento de desenhar; sem internet, as do sistema.
- **Avatar com o rosto de quem usa** fica de fora: é serviço pago de terceiros (a HeyGen, por
  exemplo), na nuvem. A porta prevista é uma cena "apresentador" que aceita um clipe gravado pela
  pessoa ou feito num serviço com a chave dela, sem o Zé depender de nenhum.
- A imagem Docker ainda não traz Chromium nem FFmpeg: na VPS, vídeos (e posts) ficam
  indisponíveis até isso entrar.
