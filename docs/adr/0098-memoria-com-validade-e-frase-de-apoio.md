# 0098 — Memória com validade e fato aprendido só com a frase de quem usa

- Data: 17/11/2026
- Status: **Aceito** (pedido de quem usa, 17/11/2026, pela comparação com o OpenMausBot).
- Reforça o [ADR 0090](0090-fatos-novos-sem-aprovacao.md), em medição até 27/11/2026.

## Contexto

Desde o ADR 0090, o fato novo que a revisão propõe entra na memória sem pedir. A proteção era
o prompt pedir fatos, e não ordens. Faltavam duas coisas, que o OpenMausBot
(`milind-soni/OpenMausBot`, Apache-2.0, `docs/memory.md`, lido em 17/11/2026) já faz:

- **Prova do que se aprendeu.** Uma pergunta ("qual o melhor plano para dez pessoas?"), um
  pedido de tarefa ou um "suponha que" podiam virar um fato sobre a pessoa. No OpenMausBot, a
  preferência ou o fato sobre quem usa só fica com as palavras em que se apoia, citadas e
  conferidas na conversa.
- **Fato com prazo.** "Está em Lisboa até sexta" ficava na memória para sempre, ocupando o
  espaço, até alguém tirar. O OpenMausBot marca a entrada com `· until <data>`, e ela deixa de
  carregar no dia seguinte.

O Hermes não faz nenhuma das duas: a memória cheia recusa o fato novo e pede para consolidar
(`tools/memory_tool_store.py`), como o Zé já fazia, e nada vence sozinho.

## Decisão

1. **Validade.** A entrada que só vale até um dia termina em ` · até DD/MM/AAAA`, o último dia
   em que vale. No dia seguinte, sai da foto do prompt e o painel a marca como "Vencida". Na
   próxima escrita daquela memória, vai para `ARQUIVO.md`, na mesma pasta, com o dia em que
   saiu. O arquivo é escrito antes da memória, então a entrada nunca fica fora dos dois. Data
   impossível ou já passada é recusada na escrita.
2. **Só vence o que tem data.** Tirar uma entrada que ainda vale continua pedindo a pessoa (ADR
   0090). A memória cheia continua recusando o fato novo; ninguém é arquivado por ser antigo.
3. **Frase de apoio.** O fato novo sobre o usuário que a revisão propõe traz o `apoio`: o trecho
   de uma fala dele, palavra por palavra, com pelo menos três palavras. O Zé confere o trecho
   nas falas da pessoa (sem contar acento e pontuação; a fala do Zé não vale). Com o apoio, o
   fato entra sozinho, e o diário guarda a frase como origem. Sem ele, vira sugestão para
   aprovar. Fato do ambiente (memória "jarvis") dispensa o apoio.
4. **O prompt da revisão** diz a data de hoje, pede a validade para o que tem prazo (nunca para
   aniversário ou data que se repete todo ano) e diz que pergunta, tarefa e hipótese nunca são
   fato sobre quem a pessoa é.

## Consequências

- A medição do ADR 0090 (fatos aprendidos sozinhos que a pessoa removeu) passa a valer só para os
  fatos com apoio a partir desta versão. Se a taxa de remoção cair, a frase de apoio funcionou.
- Menos fatos sobre a pessoa entram sozinhos; os que não têm apoio aparecem como sugestão.
- O arquivo só cresce. Ele fica na pasta da memória, fora do prompt, e pode ser lido ou apagado
  à mão.
- Fica para depois: a lembrança automática a cada pedido, que o OpenMausBot também faz (busca nas
  notas e nas conversas antigas e põe o resultado no pedido, não no prompt de sistema, para o
  cache continuar valendo). Está no plano de maturidade.
