# 0065 — Propor como PR: as melhorias do autodesenvolvimento vão para o GitHub

- Data: 06/11/2026
- Status: **Em validação** (testado com um repositório e um `gh` de mentira; falta o primeiro PR
  de verdade, pela voz).

## Contexto

O autodesenvolvimento melhora o Zé numa cópia isolada, testa e junta na pasta em uso. Nada vai
para o GitHub: a melhoria fica só nesta máquina. Em 05/11/2026, a dos contatos da agenda ficou
presa na pasta local até ser levada à mão para um PR. Quem usa quer melhorar o Zé pela voz e,
quando decidir, deixar salvo no GitHub.

O repositório é público. Uma melhoria pode, sem querer, levar dados de quem usa: em 04/11/2026 um
teste tinha o telefone real do usuário, e em 06/11/2026 o nome real de um contato entrou nos
testes e na persona (PR #105), trocado depois por um inventado.

## Decisão

1. **Propor é um passo do Zé, não da sessão.** Pela voz ("manda essa melhoria como PR",
   `modo_manutencao` com `propor`, que pede o "sim" falado, dizendo que o repositório é público) e
   pelo painel (Melhorias → "Propor como PR", com confirmação na página e só no próprio PC). A
   sessão de melhorias é instruída a não publicar sozinha e a usar só dados inventados.
2. **Na ordem, parando no primeiro não** (`zervis/oficina/proposta.py`):
   - há commits da cópia que a origem não tem (aplicados ou não), e nada sem commit;
   - os testes passam na cópia;
   - **a conferência de dados pessoais** (`zervis/oficina/vazamento.py`) não acha nada;
   - envia a branch `ze/melhoria-<data>` e abre o PR pelo `gh` desta máquina, com os commits, os
     arquivos, o que foi conferido e um aviso quando a zona protegida muda. Se o PR não abrir, a
     branch enviada é apagada.
3. **A conferência compara com os dados reais desta máquina, lidos na hora e nunca gravados**:
   números e LIDs da agenda do WhatsApp e o número conectado, nomes completos da agenda e do
   perfil, o conteúdo das chaves e tokens da configuração do Zé, a pasta pessoal, formatos
   conhecidos de chave e arquivos que não vão para um repositório (banco, chave, `.env`, perfil,
   configuração). Só as linhas acrescentadas e as mensagens dos commits contam. O achado diz o
   tipo e o lugar (arquivo e linha), nunca o valor.
4. **Depois do PR**, a CI confere, quem mantém mescla no GitHub, e o `update` traz de volta: o
   commit local é ancestral do que foi mesclado, então a pasta avança sem conflito.

## Consequências

- As melhorias por voz deixam de ficar presas numa máquina, e a CI passa a conferir cada uma.
- Rodada sobre todas as mudanças da v0.1.0 até a v0.2.0, a conferência achou o nome do contato
  (já trocado) e um identificador de contato numa mensagem de commit antiga, que fica no
  histórico: tirar exigiria reescrever o histórico público.
- Um contato salvo com um nome comum (duas palavras do dia a dia) pode barrar um PR sem dado
  real nenhum: o achado diz onde, e a sessão troca o texto.
