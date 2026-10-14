# Auditoria 3: Memória

Área 3 do checklist (`docs/checklist.md`). Um passo por vez.

**Conceito.** O que o Zé sabe, em duas camadas:

| | O que é | Onde aparece |
|---|---|---|
| **Memória curta** | Fatos curtos e aprovados, que vão em **toda** conversa: "Sobre você" (preferências, jeito de trabalhar) e "Sobre a máquina e o Zé" (notas do ambiente). Tem limite de tamanho: cheia, o Zé resume antes de gravar | Página Memória |
| **Memória longa** | Tudo o que já foi conversado: conversas por dia, linha do tempo, notas do dia e o ai-memory dos projetos. Não vai em toda conversa: o Zé **busca** quando precisa | Conversa (o dia de hoje); por voz ("o que conversamos ontem?") |
| **Memória dos projetos** | O que cada sessão de código fez, guardado por projeto pelo ai-memory: volta na próxima sessão daquele projeto. Cada sessão também mantém a própria conversa (retomada depois de reiniciar) e lê o `CLAUDE.md`/`AGENTS.md` do projeto | Página Memória (estado e páginas guardadas); a conversa, em cada sessão |
| **Sugestões** | O que o Zé percebeu numa conversa (uma correção, uma preferência) e propõe guardar como memória ou skill. Só entra com a aprovação da pessoa | Página Memória |

Um fato é memória; um procedimento ("como faço X do meu jeito") é skill (área 4).

## Achados

1. **As sugestões não apareciam no painel** (só por voz): havia uma esperando e a página dizia
   "Vazia". **Corrigido em 13/10/2026:** cartão **Sugestões** no topo da Memória, com Aprovar e
   Descartar, pelo mesmo caminho da voz (e registradas no diário de aprendizado).
2. **O que se adicionava à memória só valia na próxima conversa.** O cérebro recebe a memória como
   uma foto no começo da conversa; a pessoa adicionou "Prefiro respostas curtas e diretas e
   engraçadas", perguntou, e o Zé disse que a memória estava vazia. **Corrigido:** quando a memória
   muda no meio da conversa, o próximo pedido leva a versão nova. A página não fala mais em
   "próxima conversa".
3. **Trocar uma entrada deixava a antiga valendo na conversa.** A pessoa trocou "banana" por
   "morango" e o Zé disse que ela gostava das duas: a banana continuava na foto do começo.
   **Corrigido:** a atualização diz o que saiu ("não vale mais"). O histórico das conversas segue
   guardando o que foi dito, como diário; quem vale é a memória atual.
4. **Apagar logo depois de reiniciar não chegava.** O cérebro conecta assim que o Zé sobe e tira a
   foto da memória ali; a pessoa apagou tudo depois e o Zé ainda dizia "morango". **Corrigido:** o
   Zé guarda a foto exata que o cérebro recebeu, no momento em que recebe, e compara a cada pedido.
5. **A memória das sessões não aparecia em lugar nenhum** (o ai-memory funciona: 427 páginas em
   13/10/2026). **Feito:** cartão "Memória dos projetos" na página, com o estado e quantas páginas.

## Passos

### Passo 1. Sugestões

- **Como:** abrir Memória; ver a sugestão pendente; Aprovar (ou Descartar).
- **Esperado:** aprovada, ela vai para "Sobre você" e some das sugestões; descartada, só some.
- **Resultado:** ✅ 13/10/2026. Aprovada pelo painel; foi para "Sobre você".

### Passo 2. Adicionar e remover pelo painel

- **Como:** perguntar algo ao Zé (a conversa começa); em "Sobre você", adicionar uma preferência;
  sem começar conversa nova, "Ei Zé, o que você sabe sobre mim?". Depois remover a entrada.
- **Esperado:** a resposta já usa o que foi adicionado; removida, deixa de valer no pedido seguinte.
- **Resultado:** ❌ 13/10/2026, primeira tentativa: a memória gravou, mas o Zé não a via na
  conversa em andamento (achado 2). Corrigido; para refazer.
  Refeito: ✅ a memória nova chegou na hora; a troca banana → morango expôs o achado 3 (corrigido).

### Passo 3. Guardar pela voz

- **Como:** "Ei Zé, lembra que eu uso o Omarchy com Hyprland."
- **Esperado:** o Zé confirma (ou pede aprovação) e a entrada aparece na Memória.
- **Resultado:** ✅ 13/10/2026.

**Área fechada em 13/10/2026.**

### Passo 4. Memória longa

- **Como:** "Ei Zé, o que conversamos hoje sobre o OmniRoute?"
- **Esperado:** ele acha a conversa de hoje e resume.
- **Resultado:** ✅ 13/10/2026 (no uso): "e ontem, você tem algum registro do que conversamos?"
  trouxe o resumo certo de segunda; "antes de ontem" disse que não havia conversa nesse dia.
