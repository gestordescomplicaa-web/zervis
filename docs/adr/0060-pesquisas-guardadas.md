# 0060 — Pesquisas guardadas: a página Pesquisas e reabrir pela voz

- Data: 03/11/2026
- Status: **Em validação** (testado no Chromium com o painel de verdade; falta a pessoa usar).

## Contexto

A pesquisa profunda (ADR 0059) gravava um relatório em Markdown numa pasta que ninguém abria: pela
voz o Zé fala só o resumo, e as fontes ficavam 2 minutos na janela da Imersão. Pergunta de
03/11/2026: "por voz ele não vai falar, então onde ele vai guardar e apresentar isso?".

## Decisão

1. **Um JSON por pesquisa** em `DADOS/pesquisas/` (`zervis/pesquisa/guardadas.py`): a pergunta,
   quando, as consultas, as fontes com os trechos lidos e o resto do que a busca achou. A
   pesquisa resumida (`internet_pesquisar`, e a reserva da profunda) também, com o resumo e os
   links. No computador, para sempre, até apagar. O Markdown sai.
2. **A página Pesquisas do painel** (grupo Trabalho): a lista das mais novas, a busca (sem
   acento, na pergunta, nos títulos e nos trechos), cada pesquisa aberta com os links e os
   trechos, e apagar. Funciona no celular, como o resto do painel. O texto vem de páginas de
   terceiros: tudo é escapado e só vira link o que é http(s).
3. **Reabrir pela voz**, livres (só leem a pasta do Zé): `pesquisas_guardadas` (a lista, ou as que
   falam de um assunto) e `pesquisa_guardada` (uma inteira). "O que achamos sobre embalagens?"
   responde da pesquisa guardada, sem gastar busca, dizendo de quando ela é; se for velha para o
   assunto (preço, notícia), o Zé oferece atualizar.

## Depois

- A pesquisa como cena na Imersão (os cards das fontes, para apresentar a alguém).
