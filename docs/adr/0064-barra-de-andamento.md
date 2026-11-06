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
