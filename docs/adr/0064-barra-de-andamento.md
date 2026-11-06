# 0064 — A barra de carregamento: o que o Zé está fazendo e quanto costuma levar

- Data: 04/11/2026
- Status: **Em validação** (testado no Chromium com a página da Imersão; falta o uso por voz).

## Contexto

Quando o Zé diz "um instante", não dá para saber o que ele está fazendo nem quanto falta. Pedido de
04/11/2026: uma barra de carregamento no topo, como as de jogo.

## Decisão

1. **O passo e o tempo esperado, não um percentual inventado.** Cada ferramenta que começa grava
   em `andamento.json` (a pasta de estado da Imersão) um rótulo ("Pesquisando a fundo na
   internet") e quanto ela costuma levar: a mediana real dela na Atividade. Ao terminar, o passo
   volta a "Pensando na resposta", com a mediana do cérebro até a primeira frase (as latências).
   Sem histórico, 4 s por ferramenta e 3 s para pensar (`zervis/rosto/andamento.py`).
2. **Vale para todo cérebro**: o aviso sai do registro de ferramentas (`ferramentas.auditada`),
   por onde passam o Claude, o Codex e o local.
3. **A barra anda como num jogo** (`jarvis-andamento.js` na Imersão, `andamentoPainel` no painel):
   começa quando o Zé passa a pensar, avança rápido e desacelera rumo a 95% conforme o tempo
   esperado de cada passo, e só completa quando a resposta começa. A frase de espera ("um
   instante") fala no meio: a barra espera 1,5 s antes de completar.
4. **Na Imersão e no painel**, no topo, com o rótulo e os segundos ("Pesquisando na internet… 12 s").
   O `GET /orb` da Imersão e o batimento do painel levam o passo junto com o estado.
5. **O visual é um holograma, como as apresentações do Zé** (pedido de 05/11/2026: a primeira
   versão, um fio no topo com uma pílula, não agradou). Um painel pequeno no topo, no centro, com
   a mesma linguagem dos painéis do `jarvis-apresentacao.css`: cantoneiras, linhas de varredura,
   um brilho que passa, e ele se materializa a partir de uma linha e se desfaz do mesmo jeito.
   Dentro: "ZÉ · PROCESSANDO" com o relógio (T+00:07), o passo em letra grande com a
   porcentagem, uma barra em células inclinadas que acendem como num jogo, com uma cabeça
   branca piscando na ponta, a régua 00–100 e o rastro dos passos ("✓ Pensando ✓ Pesquisando
   ▸ Lendo as páginas ≈ 6 s"). Um feixe tracejado desce do painel até o Zé. Ao responder, as
   células ficam brancas, aparece "Resposta pronta" e o painel se desfaz. As cores vêm do tema
   (`--jv-acento-rgb`). No painel, a mesma peça em versão compacta (sem régua, rastro e feixe),
   nas cores do painel. Um pedido novo sempre começa do zero: antes, ele herdava o ponto onde o
   anterior tinha parado.
