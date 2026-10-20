---
name: systematic-debugging
description: Investigar uma falha pelo comportamento reproduzível e corrigir sua causa raiz.
sessoes: sim
---
# Depuração sistemática

## Do meu jeito
- Separe fatos observados de hipóteses.
- Não esconda o sintoma nem amplie a tarefa para refatorações sem relação.
- Se não conseguir reproduzir, diga o que verificou e o que falta para confirmar.

## Passos
1. Reproduza a falha com o menor caso possível e registre o resultado esperado e o observado.
2. Siga o fluxo de dados e controle até encontrar onde o comportamento diverge.
3. Formule uma causa provável e verifique-a com uma mudança ou teste pequeno.
4. Corrija a causa com a menor alteração coerente com os padrões do projeto.
5. Adicione ou ajuste um teste de regressão e rode primeiro as verificações relacionadas.

## Pronto quando
- A causa está sustentada por evidência, não apenas por correlação.
- O teste reproduz a falha antes da correção e passa depois dela.
- A correção não introduz mudanças fora do escopo.
