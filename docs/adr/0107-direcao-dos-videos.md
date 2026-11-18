# 0107 — Direção dos vídeos: o Opus dirige, o tempo vem da voz

- Data: 18/11/2026
- Status: **Aceito** (pedido de quem usa, 18/11/2026).
- Fase 1 da evolução dos vídeos ([ADR 0106](0106-videos-de-marketing.md)).

## Contexto

O primeiro vídeo feito pelo Zé para a marca de quem usa saiu bonito, mas não convenceu:

- **A tela repetia a fala.** No gancho apareciam o título, uma linha de apoio e a legenda da mesma
  frase, ao mesmo tempo; nas outras cenas, a legenda inteira embaixo de um título parecido.
- **O tempo era estimado.** A legenda e a entrada dos elementos seguiam o tamanho das palavras,
  não a voz: o item da lista entrava antes ou depois de ser dito.
- **Todas as cenas tinham a mesma composição**, sem movimento de câmera nem transição de verdade:
  cara de apresentação de slides.
- **O roteiro era do Sonnet**, por cópia do caminho dos posts (modelo menor em segundo plano).

Quem usa trouxe uma especificação de "direção audiovisual" que pedia o HyperFrames como motor.
O motor do Zé é próprio (ADR 0106); o HyperFrames só existia como skills do Claude Code. Ficou
decidido manter o motor próprio, trazer para ele as técnicas de movimento, e oferecer o
HyperFrames como segundo motor, à escolha, num passo seguinte.

## Decisão

1. **O Opus 5.5 dirige** (com raciocínio de até 3.000 tokens), e o modelo pode ser trocado em
   Marketing. O roteiro vira um **plano de direção**: o objetivo e o público do vídeo, e, por cena,
   o tipo, a composição, o movimento de câmera (`empurra`, `afasta`, `desliza`, `parado`), a
   transição (`corte`, `mascara`, `deslize`, `zoom`) e em que palavra da fala cada elemento entra
   (`quando`). Um "quando" que não está na fala é descartado.
2. **O tempo vem da voz.** Cada fala gravada vai ao Deepgram (a chave da escuta), que devolve o
   início e o fim de cada palavra; `narracao.alinhar` casa o que foi ouvido com o roteiro (o que não
   casa, como "13" dito "treze", fica entre as vizinhas). Sem a chave, volta a estimativa.
3. **A tela não repete a fala.** Gancho e frase são a própria fala em tipografia, palavra por
   palavra no tempo da voz, sem legenda embaixo. Nas cenas visuais, a legenda vem em blocos curtos
   (até 6 palavras, quebrando na pontuação), e a tela mostra só a ideia, em poucas palavras.
4. **Câmera e transições de verdade.** Cada cena tem um miolo com o movimento de câmera e um fundo
   próprio (as mesmas manchas de luz, no mesmo tempo), para a cena que entra cobrir a que sai: a
   máscara abre em círculo, o deslize empurra com desfoque de velocidade, o zoom atravessa, e o
   corte seco dá um soco de câmera na batida. Nada de dupla exposição.
5. **Composições novas:** gancho e frase à esquerda (tipografia grande, alinhada), lista "um por
   vez" (um item enorme de cada vez, com marcadores), antes e depois "dividido" (o depois abre como
   cortina, com o fio aceso) e número "gigante".
6. **Duração escolhida:** 15, 30, 45 ou 60 s; o número de cenas e de palavras acompanha.

## Consequências

- Um vídeo custa uma chamada ao Opus (o plano), uma síntese de voz por fala e uma transcrição curta
  por fala no Deepgram. O tempo de máquina não muda (cerca de 1 minuto).
- Os estilos de quem usa continuam valendo; as cenas novas usam as mesmas variáveis da marca.
- Próximos passos: o motor HyperFrames à escolha (o mesmo plano, montado por um agente com as
  skills dele), imagens com sentido nas cenas, a conferência automática antes da entrega, e editar
  um vídeo gravado por quem usa.
