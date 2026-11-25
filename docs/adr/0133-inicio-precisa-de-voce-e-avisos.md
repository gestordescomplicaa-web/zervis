# 0133 — O Início pela voz, o "Precisa de você" e a central de avisos

- Data: 25/11/2026
- Status: **Aceito** (protótipo aprovado; segundo passo de `docs/plano-design.md`).
- Segue o ADR 0132 (a casca nova).

## Contexto

O Início mostrava números do dia e três cartões; o que esperava quem usa ficava espalhado: a
aprovação do WhatsApp na Conversa, o lead só na voz, a permissão na sessão, a mensagem da
prospecção, o vídeo pronto no Marketing. Os avisos do Zé apareciam num texto solto, que sumia
sem deixar rastro. Quem usa pediu "eventos claros e notificados em tela" e a voz no centro.

## Decisão

1. **`zervis/nucleo/precisa.py`** junta o que espera quem usa: aprovações do WhatsApp, leads,
   permissões e perguntas das sessões, sessões paradas, mensagens da prospecção, vídeos e posts
   para revisar (até uma semana), automações com erro, melhorias, sugestões de memória e versão
   nova. Do mais grave ao menos; no mesmo nível, o que espera há mais tempo primeiro. Cada fonte
   que falha fica de fora, sem derrubar a lista. Nada ali decide: cada item leva à página que
   resolve (o lead, ao WhatsApp); só a aprovação do WhatsApp se resolve ali, pelo mesmo pedido
   da Conversa (`conversa/aprovacao`).
2. **O Início:** o anel grande com o estado do Zé, a saudação, como chamar ("Ei Zé" ou Falar) e
   quatro pedidos de exemplo que vão ao Zé como se escritos (a resposta aparece na Conversa);
   "Precisa de você", "O Zé agora" (sessões trabalhando, o que o Marketing cria, a próxima
   mensagem da prospecção, as próximas automações), o Foco e os números de hoje.
3. **O sino** no topo conta os itens; o painel ao lado lista-os e os avisos do Zé de hoje
   (leitura `precisa`, a cada 30 s com a aba visível). O aviso que o Zé não falou entra na tela
   com o anel e Fechar, e fica no sino.
4. **Pela voz:** o `ze_sobre` leva a mesma lista; "o que precisa de mim?" tem resposta.
5. **Peso:** o sino e o painel de avisos carregam logo depois da abertura (`import()` em
   `principal.js`), fora do orçamento de 130 KB.

## Consequências

- Uma fonte nova de pendência (outra página que pede o sim) entra em `precisa.FONTES`.
- A Imersão e a abertura do dia (`zervis/abertura/`) não mudam.
