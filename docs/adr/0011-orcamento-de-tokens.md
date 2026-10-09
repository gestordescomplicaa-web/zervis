# 0011 — Orçamento de tokens

- Data: 06/10/2026
- Status: **Aceito** (pedido do usuário: "temos que ter cuidado com isso")

## Contexto
Na assinatura não se paga por token, mas tudo gasta as janelas de uso (5 h e semana), as mesmas
das sessões de código no Orca. O Hermes é famoso pelo autoaprimoramento e também pelo consumo:
a revisão a cada 10 turnos relê a conversa inteira, e a lista de skills vai em todo prompt.

**Medido em 06/10/2026** (Claude Sonnet 5.5, persona + memória + 16 ferramentas): um turno lê
~6,4 mil tokens de contexto, ~99% do cache; o primeiro turno de uma sessão cria ~3,2 mil de cache;
a resposta escreve 16 a 70 tokens.

## Decisão
1. **Medir sempre:** cada resposta soma no consumo do dia (log, `status.json` e o relatório
   "como estão as baterias?").
2. **Conversa parada recomeça:** 30 min sem pedido, a próxima pergunta abre sessão nova (a memória
   fica). Sessão do dia inteiro relê um histórico cada vez maior a cada turno.
3. **Nada que mude no meio da sessão vai no começo do prompt:** a memória é foto congelada; o que é
   estável vem antes do que varia, para o cache valer.
4. **Skills (Fase 6):** no prompt, só uma linha por skill (nome e descrição, com teto total); o
   corpo é lido sob demanda.
5. **Revisão em segundo plano (Fase 6):** nunca "a cada 10 turnos" às cegas. Roda no fim de uma
   conversa só se houve correção do usuário ou conversa longa, com modelo menor (Haiku), só com os
   turnos daquela conversa e um teto de vezes por dia.
6. **MCPs externos:** cada servidor ligado põe a descrição das ferramentas em todo turno. Só os
   escolhidos, com lista de ferramentas permitidas, e o custo dele aparece no consumo.
7. **Automações (Fase 7):** lembrete simples roda em modo script (zero modelo); modelo só quando
   precisar pensar.

## Consequências
- Cada fase nova mostra no consumo do dia quanto passou a custar; se algo pesar, desliga-se ali.
- **Eficácia primeiro (o usuário, 06/10/2026):** a economia não pode deixar o JARVIS aprendendo e
  acertando menos que o Hermes. Se uma regra acima (revisão só no fim da conversa, modelo menor,
  skills resumidas) fizer ele deixar de aprender algo que o Hermes aprenderia, a regra volta para o
  comportamento do Hermes (revisão a cada 10 turnos com o modelo principal) e isto é anotado aqui
  com o caso que mostrou a perda.

### Revisão: prova de eficácia × custo (06/10/2026)
Mesma conversa com duas correções do usuário (estilo: "não explique o pytest"; método: "nos
testes, já mande corrigir"):

| Modelo e pensamento | Tempo | Escreveu | O que aprendeu |
|---|---|---|---|
| Haiku, pensamento livre | 27 s | 2.744 | só uma skill (estilo ficou dentro dela) |
| Haiku, sem pensar | 4 s | 213 | só uma nota presa ao projeto (perdeu o estilo) |
| **Haiku, 1.500 de orçamento** | 11 s | 831 | **estilo na memória + skill de classe (como o Hermes)** |
| Sonnet, sem pensar ou adaptativo | 4 s | ~180 | as duas na memória, gastando o modelo principal |

Escolha: Haiku com 1.500 de orçamento (`revisao.pensamento_tokens`).
