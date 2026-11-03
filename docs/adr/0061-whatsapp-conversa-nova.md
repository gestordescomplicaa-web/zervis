# 0061 — WhatsApp: começar uma conversa nova pelo número, com o sim que confere a pessoa

- Data: 03/11/2026
- Status: **Em validação** (testado com o WhatsApp falso; falta um envio de verdade).

## Contexto

O Zé só respondia a quem já tinha escrito (ADR 0054). Caso de 03/11/2026: a pesquisa profunda
achou o número de uma empresa, o usuário pediu "manda um oi para essa empresa no WhatsApp" e o Zé
disse que só o usuário podia começar a conversa. O pedido: "se eu pedir para mandar uma mensagem,
seja para quem for, ele deve confirmar se é para a pessoa X; se for, ele inicia e envia".

## Decisão

1. **`whatsapp_enviar`**: uma conversa nova pelo número, com o nome de quem é e o texto ditado.
   Passa pela aprovação falada, que diz o nome, o número e o texto, e pergunta se é para aquela
   pessoa mesmo: "Vou começar uma conversa no WhatsApp com Embalagens G6, no número 11
   98765-4321, e mandar: Oi, tudo bem. É para Embalagens G6 mesmo? Envio?".
2. **O número**: com o DDD, sem o "+" é do Brasil (ganha o 55); de fora, com o "+" e o código do
   país. Celular do Brasil vai com e sem o nono dígito: o WaCalls confere quais existem no
   WhatsApp (`IsOnWhatsApp`) e envia ao único que existir; número fora do WhatsApp volta como
   "Esse número não está no WhatsApp".
3. **Cada "sim" é um envio** (a chave de idempotência é nova a cada aprovação) e o contato entra
   na lista de prioridade por 24 horas, pelo número: quando responder, o Zé avisa (ADR 0055).
4. **Continua**: grupo nunca; quem já está na caixa segue pelo `whatsapp_responder`; o texto é o
   que o usuário ditou, sem o Zé inventar; o número vem do usuário, de uma pesquisa ou de um
   cadastro, e o Zé nunca diz que só o usuário pode começar uma conversa.
