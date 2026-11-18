# 0104 — A conversa pelo WhatsApp é a mesma, e a aprovação é no painel

- Data: 18/11/2026
- Status: **Aceito** (decisão com quem usa, 18/11/2026).
- Complementa o [ADR 0102](0102-conversa-pelo-whatsapp.md) e o
  [ADR 0103](0103-audio-na-conversa-com-o-ze.md). Prepara a regra dos grupos das empresas
  ([plano](../plano-empresas.md)).

## Contexto

Pelo ADR 0102, o seu número fala com o Zé pelo WhatsApp num cérebro próprio, e toda ação com
efeito era negada ("só pela voz ou pelo painel"). Isso deixava dois buracos:

- **Duas conversas.** O Zé do WhatsApp não sabia o que foi dito pela voz ou pelo painel, e o da
  voz não sabia o que foi dito pelo WhatsApp, embora a aba Conversa mostrasse as duas.
- **Nenhum jeito de aprovar.** A aprovação existia só falada; com o Zé inativo, um pedido com
  efeito feito pelo WhatsApp não tinha como seguir.

Aprovar pelo próprio WhatsApp perde a segurança: quem está com o celular na mão (ou quem clonou o
número) não é, necessariamente, quem usa. O painel e o app exigem login.

## Decisão

1. **Uma conversa só.** Cada pedido do WhatsApp leva, antes do texto, o que foi dito pela voz e
   pelo painel desde o pedido anterior (`<conversa>...</conversa>`); um cérebro recém-subido leva
   os últimos 8 turnos do dia, de onde vierem. O pedido seguinte da voz leva o que foi dito pelo
   WhatsApp desde o anterior (no máximo 6 turnos). Os turnos do WhatsApp ficam gravados com a
   origem, e a aba Conversa marca cada um com "WhatsApp".
2. **O WhatsApp lê e anota.** As ferramentas de leitura e o lembrete seguem livres, como na voz.
   Acrescentar à memória passa sem o "sim"; trocar e remover pedem. Num turno de fora (depois de
   ler texto de terceiros, ADR 0073), até acrescentar pede.
3. **O que tem efeito espera o painel.** O Zé manda ao seu número "Aprovação pendente no painel
   do Zé (Conversa): <a ação>", e a aba Conversa mostra a ação com **Aprovar** e **Negar**. Ela
   roda só se aprovada ali, em até 10 minutos; depois disso, é negada. O WhatsApp nunca aprova
   nada: responder "sim" por lá é só uma mensagem.
4. **Uma de cada vez.** O cérebro do WhatsApp responde um pedido por vez: enquanto uma ação
   espera, as mensagens seguintes esperam na fila (até 10).
5. **Em memória.** As aprovações pendentes não sobrevivem a um reinício (o cérebro que pediu
   também acabou); desligar o Zé nega todas.

## Consequências

- A ação de risco 3, que exige a frase exata dita, não passa pelo painel: o botão não fala a
  frase, e a ação é negada com o motivo. Essas ficam só com a voz.
- O app de voz do Android não recebe a aprovação como notificação: ele só fala com o Zé enquanto
  está conectado. O painel aberto pelo celular (com login) é o caminho.
- Cada pedido do WhatsApp e cada pedido da voz leem a conversa do dia no SQLite local: uma
  consulta pequena, sem rede, feita junto do envio ao cérebro.
- Os grupos das empresas herdam a regra: o que alguém pede no grupo vira aviso para quem usa, e
  nenhum grupo aprova nada.
