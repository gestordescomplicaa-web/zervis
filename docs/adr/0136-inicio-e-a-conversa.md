# 0136 — O Início é a conversa com o Zé

- Data: 25/11/2026
- Status: **Aceito** (protótipo aprovado em imagens; quinto passo de `docs/plano-design.md`).
- Segue os ADRs 0132 (a casca) e 0133 (o Início pela voz e o "Precisa de você").

## Contexto

O Início e a Conversa eram duas páginas: no Início, o resumo do dia e pedidos de exemplo que
levavam para a Conversa; na Conversa, o chat. Quem acaba de instalar e configurar o modelo (por
assinatura ou chave de API) caía num painel de números e não sabia por onde começar. Quem usa pediu
as duas coisas numa tela só: o chat aberto, como num produto de chat com agente, sem perder o que o
Zé está fazendo nem o que espera uma decisão.

## Decisão

1. **O Início é o chat** (`paginas/inicio.js`, com o chat de `paginas/conversa.js`). Sem conversa
   no dia, a tela mostra o anel do Zé, a saudação, o campo de escrever (com o microfone e o
   enviar) e as sugestões, no meio da tela. A primeira mensagem, escrita ou tocada numa sugestão,
   vira o chat: o fio de hoje no meio e o campo embaixo.
2. **Ao lado do chat**, o que era o resto do Início: "Precisa de você", "O Zé agora", o Foco e os
   números de hoje, com o consumo detalhado do dia. A lateral é relida a cada 15 s sem tocar no
   chat. As aprovações pedidas pelo WhatsApp ficam no próprio chat, onde se resolvem, e saem da
   lista ao lado.
3. **Tela menor** (até 1180 px): sem conversa, o resumo vem abaixo das sugestões; na conversa, ele
   sai da tela e fica no sino do topo, que já conta o que espera você.
4. **A Conversa sai do menu.** O endereço `#conversa` leva ao Início; as chamadas ao Zé
   (`conversa`, `conversa/escrever`, `conversa/aprovacao`) não mudam. No mapa do Zé (ADR 0128), o
   Início passa a dizer que é a conversa e ganha a ferramenta `historico_buscar`.

## Consequências

- O que se escreve no Início segue o mesmo caminho da fala, como na Conversa (ADR 0104 para o
  WhatsApp); a fala e o Silencioso aparecem no mesmo fio.
- O resumo do dia deixou de ser a primeira coisa da tela: quem quer só os números os vê ao lado,
  ou pergunta ("o que precisa de mim?").
