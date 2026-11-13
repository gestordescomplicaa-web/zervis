# 0092 — O blog no piloto automático: o Zé escreve, abre o PR e publica com o "aprovado"

- Data: 13/11/2026
- Status: **Em validação**: testado com um repositório e um `gh` de mentira; o caminho de
  publicar (commit direto na base, com o autor de quem usa) foi provado à mão no site real em
  13/11/2026.

## Contexto

O primeiro artigo pela aba Marketing (ADR 0091) chegou até o PR, mas não foi ao ar sozinho:

- a sessão parou pedindo aprovação para instalar as dependências e validar;
- o artigo ficou preso nos marcadores de experiência real, sem resposta;
- o merge pelo botão do GitHub foi bloqueado pela Vercel. No plano Hobby com repositório privado,
  só publica o commit cujo autor é a conta dona; o commit de merge leva o autor de quem clicou.

Quem usa quer pedir "dois artigos por semana" e só aprovar.

## Decisão

1. **Automação do tipo `artigo`** (`automacoes/jobs.py`): na hora, o Zé pede um artigo do blog,
   sem tema (a sessão escolhe pelo manual do site). Aprovada uma vez, quando é agendada:
   `marketing_agendar` pela voz ou "Artigos automáticos" na aba Marketing.
2. **A sessão não para:** o pedido libera, só naquela sessão (`livres.json`, lido por
   `agentes.livres_da_sessao`), o git da cópia e os comandos que o site declara no `zervis.json`
   (`instalar` e `validar`). Comando com caractere de shell é recusado. A cópia é isolada e
   protegida, sem como enviar nada.
3. **O PR abre sozinho** quando a sessão termina, e o Zé avisa.
4. **Publicar é o "aprovado"** (`marketing_publicar` ou "Publicar" no painel):
   - Num artigo, a sessão tira o rascunho, põe a data de hoje e encaixa as respostas às perguntas
     de experiência, se vierem. Sem respostas, os trechos saem.
   - Quando a sessão termina, o Zé confere que não sobrou rascunho nem marcador, junta a base se
     ela andou (rebase) e envia a branch direto à base, sem commit de merge. Assim o autor é o
     dos commits, que o deploy aceita.
   - O PR fica igual à base e o GitHub o dá como mesclado.
   - Numa mudança no site, publica na hora.
5. **O deploy é conferido:** o Zé lê os deploys de produção do commit pelo GitHub e avisa
   "está no ar", "o deploy falhou (motivo)" ou que não houve resposta em 10 minutos.
6. **Os hooks do git do site não rodam** nos envios e no rebase que o Zé faz, porque estariam fora
   do isolamento.

## Consequências

- Se a base tiver proteção que exige PR, o envio direto é recusado e o Zé diz para publicar pelo
  GitHub com "Rebase and merge".
- As perguntas de experiência só entram se a pessoa responder antes de aprovar. O contrato do
  site passa a tratá-las como opcionais.
- Imagens e capa ficam para depois, no site (capa gerada pelo título).
