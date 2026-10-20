---
name: test-driven-development
description: Desenvolver uma mudança guiada por um teste pequeno que descreve o comportamento esperado.
sessoes: sim
---
# Desenvolvimento guiado por testes

## Do meu jeito
- Use as ferramentas e convenções de teste que o repositório já adotou.
- Prefira verificar comportamento observável a detalhes internos de implementação.
- Mantenha cada mudança focada no pedido.

## Passos
1. Identifique o comportamento pedido e um caso de teste que o demonstre.
2. Escreva o teste e confirme que ele falha pelo motivo esperado.
3. Implemente apenas o necessário para fazer o teste passar.
4. Rode o teste específico e depois as verificações adequadas ao escopo.
5. Refatore somente se isso simplificar a solução sem alterar o comportamento.

## Pronto quando
- Há um teste relevante para o comportamento novo ou corrigido.
- O teste passou e as verificações relacionadas não apontam regressões.
- Limitações de teste ou validação estão descritas com clareza.
