# 0118 — Os comentários do Instagram viram conversa no direct

- Data: 23/11/2026
- Status: **Aceito** (pedido de quem usa; teste controlado com uma conta de fora aprovado em
  23/11/2026).
- Etapa 1 de 4 do funil do Instagram. Usa a conta dos posts ([ADR 0093](0093-posts-do-instagram.md)).

## Contexto

Quem usa é gestor de automação e IA e quer converter quem comenta (um empresário) numa conversa
de diagnóstico e numa reunião, sem depender de uma palavra-chave e sem entregar brinde técnico,
que atrai público só técnico. A conta já tinha, pelo Login do Instagram, as permissões de
comentários e de mensagens; um teste com uma conta sem papel no aplicativo da Meta provou a
resposta pública e a resposta privada.

## Decisão

1. **Ligado na página** (Marketing, cartão "Comentários do Instagram"; desligado por padrão), o Zé
   confere os 12 posts mais recentes a cada dois minutos, numa thread do agendador.
2. **Todo comentário** novo (feito depois de ligar, de outra conta, até 7 dias, a janela da Meta)
   ganha uma resposta pública curta e variada e, no direct, a **resposta privada** da Meta (uma
   por comentário).
3. **A abertura** é escrita pelo Haiku a partir do comentário, do post e do que a empresa faz (o
   atendente): agradece citando o comentário, diz em meia frase o que a empresa faz, reconhece uma
   pergunta se houver e faz uma pergunta de diagnóstico (o negócio e onde perde tempo). O
   comentário vai entre `<<<` e `>>>`, como dado. Sem o modelo, vai uma abertura de reserva.
4. **Sem insistência:** quem recebeu uma abertura nos últimos 3 dias ganha só a resposta pública.
   Cada comentário é respondido uma vez, gravado a cada envio (se o Zé cair no meio, ninguém
   recebe duas vezes). Uma recusa da Meta fica registrada e não se repete.
5. Quem usa recebe o aviso "Respondi N comentário(s) no Instagram: @...".

## Consequências

- A conversa que vem depois (a pessoa responde no direct) é a etapa 2: o atendente de pré-vendas.
- Para quem não segue a conta, a mensagem pode cair em "Solicitações".
