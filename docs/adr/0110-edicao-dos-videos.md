# 0110 — A edição dos vídeos: menos cara de vídeo gerado

- Data: 18/11/2026
- Status: **Aceito** (pedido de quem usa, 18/11/2026).
- Continua o [ADR 0107](0107-direcao-dos-videos.md). As regras vêm das referências de movimento do
  HyperFrames (`hyperframes/references/motion.md` e `types/vertical.md`), aplicadas ao motor
  próprio, sem trocar de motor nem custar mais por vídeo.

## Contexto

Com a direção do Opus e o tempo real da voz, os vídeos ficaram certos, mas quem usa achou a edição
limitada. As referências de movimento do HyperFrames listam o que faz um vídeo parecer gerado, e o
motor fazia quase tudo isso: tudo entrando com fade e subindo, todas as cenas entrando do mesmo
jeito, um zoom lento e eterno em cada cena, o brilho "respirando", o anel de clique no botão.

## Decisão

1. **Entradas variadas** (`Ze.revela`): desfoque parado, cinza para a cor ("tinta"), queda com peso,
   chegada de lado com rastro, cortina (máscara) e giro em perspectiva. Cada cena e cada composição
   tem a sua; o que assenta fica parado. Chegadas com cauda longa (expo.out), saídas curtas.
2. **Câmera com intenção:** "empurra" virou um soco de câmera na palavra de destaque, no instante em
   que ela é dita; "afasta" e "desliza" mexem só na chegada. Sem zoom lento eterno.
3. **Transições com causa:** a íris abre do elemento em foco da cena que sai; o zoom atravessa esse
   elemento (acelerando, com desfoque); o chicote passa as duas cenas borradas na velocidade; a cor
   da marca inunda a tela para mudar de assunto (nova, `cor`); o corte seco escurece a cena nos
   três últimos quadros e entra com um soco. Cada cena diz o seu `foco`.
4. **Composições novas:** o gancho "gigante" (uma palavra por linha, enorme, caindo com peso; só
   com fala de até 7 palavras) e a frase "cheia" (a tela inteira na cor da marca, o texto
   acendendo do cinza). O destaque ganhou um marca-texto que corre por baixo depois de dito.
5. **3D onde é conteúdo gerado:** o logo da marca extrudado (12 camadas, a lateral mais escura),
   girando até ficar de frente com a luz correndo na face; os cartões dos passos, da lista e da
   conversa girando em perspectiva; o número crescendo enquanto conta, com um estalo ao chegar.
   Tela de produto nunca é inclinada.
6. **Cenas de arte em vez de cartões** (`web/artes.js`): o diretor prefere metáforas animadas.
   "icone" desenha um conceito enorme, traço por traço, com ondas e faíscas; "conexao" liga nós
   por linhas que se desenham, com dados correndo; "hub" põe a marca (ou um ícone) no centro e a
   constelação em volta, ligada a ele, girando devagar; "caos" mostra ícones espalhados e tremendo
   que se organizam na palavra-chave. Os ícones são os 63 da Lucide que o Zé já traz: o modelo só
   escolhe o nome. Cartões de texto, no máximo dois por vídeo. Todas as cenas ganham um piso em
   perspectiva andando ao fundo.
7. **Legenda de Reels:** grupos de 3 a 5 palavras, a palavra da vez numa pílula da cor da marca, e
   nada da cena nova por cima da cena que sai durante a transição.

## Consequências

- O tempo de máquina e o custo por vídeo não mudam (o plano continua uma chamada ao Opus).
- Os estilos de quem usa continuam valendo; quem escreve cenas próprias ganha `Ze.revela`,
  `Ze.sai`, `Ze.letras` e o `foco` das transições.
- A música continua composta em código; a referência do HyperFrames recomenda música de catálogo
  (precisa de conta na HeyGen). Fica para um passo seguinte, como opção.
