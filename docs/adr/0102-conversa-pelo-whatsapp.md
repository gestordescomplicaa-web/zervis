# 0102 — Conversar com o Zé pelo WhatsApp

- Data: 18/11/2026
- Status: **Aceito** (pedido de quem usa, 18/11/2026). Exceção ao congelamento da Fase B, como
  os ADRs 0091 e 0098, com os testes na porta de qualidade. **Revisto no mesmo dia:** o chat
  "Você" deu lugar ao número do Zé (ver "Revisão" no fim).
- Relacionados: [ADR 0031](0031-atendimento-whatsapp-e-telefonia.md) (a Central e o WaCalls),
  [ADR 0054](0054-whatsapp-do-ze-recepcionista.md) e [ADR 0056](0056-arquivo-do-whatsapp.md) (a
  caixa e o arquivo), [ADR 0073](0073-entrada-de-fora.md) (o que vem de terceiros).

## Contexto

Muita gente quer falar com o Zé sem abrir o painel nem o app: pelo WhatsApp que já usa. O Zé já
tem o WhatsApp conectado (o WaCalls, pela Central), mas só lia as conversas para a caixa de
entrada e respondia aos leads pelo agente de atendimento, que não alcança o Zé.

Um segundo número só para o Zé daria notificação às respostas, mas exige outro chip e outro
pareamento. O chat "Você" (a conversa do número consigo mesmo) já existe em todo WhatsApp.

A aba Conversa passa pela máquina de voz, que recusa pedidos com o Zé inativo (tela bloqueada ou
a pessoa fora). Quem escreve pelo WhatsApp está, quase sempre, longe do computador.

## Decisão

1. **O WaCalls marca o chat "Você"** (`is_self`): a mensagem enviada pelo próprio número, numa
   conversa privada cujo outro lado é ele mesmo, na forma de telefone ou de LID. O Zé confere de
   novo (só a mensagem enviada, nunca em grupo). Mensagem de qualquer outra pessoa segue como
   entrada de fora (ADR 0073).
2. **A Central faz dela um pedido** (o evento `pedido`): não vai ao arquivo nem ao agente de
   atendimento.
3. **Um cérebro próprio responde** (`zervis/cerebro/por_mensagem.py`): o mesmo provedor, a mesma
   persona (com uma nota de que o pedido veio escrito pelo WhatsApp) e as mesmas ferramentas,
   numa sessão separada, sem a máquina de voz. Funciona com o Zé inativo. Um pedido por vez, na
   ordem; no máximo 10 na fila. O cérebro sobe no primeiro pedido e fecha depois de 30 minutos
   parado.
4. **A resposta vai ao mesmo chat**, em mensagens de até 1.900 caracteres. Ela volta pelo
   WaCalls como mensagem sua: a Central guarda o resumo do texto que enviou e descarta o eco por
   até 5 minutos. Sem isso, o Zé responderia a si mesmo sem parar.
5. **Nada com efeito é confirmado pelo WhatsApp.** O que pede aprovação é negado, e o modelo diz
   que precisa da voz ou do painel. Quem pega o celular desbloqueado, ou um WhatsApp Web esquecido
   aberto, só consegue perguntar, não executar (essência, item 5). O que a política já libera sem
   pergunta (risco baixo) segue liberado.
6. **Ligado no painel, desligado de início:** "Conversa com o Zé", no cartão do WhatsApp. Muita
   gente usa o chat "Você" para anotações, e cada uma viraria um pedido. (Revisto: ver o fim.)
7. **Registro:** cada pedido entra na Atividade (`origem: whatsapp`), na conversa do dia (que
   alimenta a memória) e no consumo.
8. **Por enquanto, só texto.** Áudio, foto ou documento recebem "Por enquanto, só mensagens de
   texto." O WaCalls não baixa mídia (decisão de 13/08/2026); o áudio no chat "Você" é a próxima
   etapa.

## Consequências

- O alcance cresce sem app novo: o Zé fica no WhatsApp de quem usa, de qualquer lugar.
- O WhatsApp não notifica as mensagens da própria conta: a resposta aparece quando a pessoa abre
  o chat. Um número só para o Zé resolveria; fica para depois, se fizer falta.
- Pedido que chega com mais de 10 minutos de atraso (o WhatsApp entregou depois de uma queda)
  não roda.
- Duas sessões do cérebro podem rodar ao mesmo tempo (a da voz e a do WhatsApp), com o consumo
  das duas.

## Revisão de 18/11/2026: o número do Zé e o seu número autorizado

A prova no número de quem usa mostrou que o chat "Você" não serve: as mensagens nos dois sentidos
aparecem como enviadas pela própria conta, sem notificação, e a conversa não parece uma conversa
com um assistente. Fica como nos agentes comparados (OpenClaw, Hermes): o Zé tem o próprio número,
e você escreve a ele do seu.

1. **O número conectado ao Zé é o do Zé.** No painel, "Conversa com o Zé" leva o interruptor e o
   **seu número**: só a mensagem que chega desse número, numa conversa privada, vira o evento
   `pedido`. O número vem do WhatsApp (o remetente é autenticado por ele); com ou sem o nono
   dígito vale o mesmo. Sem o número (só o LID), a mensagem é de fora.
2. **Essa conversa não vai ao arquivo nem ao agente de atendimento**, nos dois sentidos: a
   resposta do Zé é uma mensagem enviada nela, e não precisa mais do descarte de eco.
3. **Saem a marca `is_self` do WaCalls e o descarte de eco da Central**, que só existiam para o
   chat "Você".
4. **A entrega não espera o tique:** o WaCalls levava as mensagens ao Zé em lotes a cada 5 s, e
   o pedido esperava até 5 s antes de chegar. Agora cada mensagem nova acorda a entrega na hora;
   o tique segue para as reentregas.
5. O resto da decisão vale como estava: o cérebro próprio, um pedido por vez, nada com efeito
   confirmado pelo WhatsApp, o registro, só texto por enquanto.

Consequência: com o número do Zé conectado, a caixa de entrada, os avisos de lead e o agente de
atendimento passam a ser os desse número, não os do seu WhatsApp pessoal. Ter os dois ao mesmo
tempo pede o Zé com duas sessões do WaCalls (ele aceita várias; o Zé usa só a primeira).
