# 0055 — A lista de prioridade do WhatsApp: quem o Zé vigia em tempo real

- Data: 03/11/2026
- Status: **Em validação** (testado com o WhatsApp simulado; falta o número de verdade).
- Sobre a caixa de entrada ([ADR 0054](0054-whatsapp-do-ze-recepcionista.md)) e as pendências
  ([ADR 0053](0053-leads-do-whatsapp-pela-voz.md)).

## Contexto

Depois do primeiro envio de verdade pelo Zé (03/11/2026), faltava o outro lado: ele avisava o lead
qualificado e respondia quando pedido, mas não percebia quando a pessoa respondia ao que ele tinha
mandado, nem vigiava um contato que você pedisse. O pedido: "fique monitorando esse número em
tempo real e me avise qualquer coisa", uma lista de prioridade que o Zé não esquece, e "não
monitora mais" para tirar.

## Decisão

1. **A lista** (`zervis/avisos/prioridade.py`, `<estado>/whatsapp-prioridade.json`, 0600), até 50:
   - **pedido**: "monitora a Ana", ou um número dito com o DDD. Fica até você tirar.
   - **resposta**: quem o Zé respondeu por você entra sozinho, por 24 horas; a primeira mensagem
     da pessoa avisa ("a Ana respondeu: ...") e a espera acaba. Quem já está de vez continua.
2. **Mensagem de quem está na lista** vira pendência na hora, com o motivo "prioridade" ou
   "resposta": aviso lido, notificação no celular, lembrete de 10 em 10 minutos até você responder.
   Não passa pelo julgamento de lead, e vale com os avisos de lead desligados (esses só calam os
   lembretes de lead).
3. **O número é comparado como se fala**: com ou sem o código do país e, no Brasil, com ou sem o
   nono dígito (o WhatsApp guarda muitos sem ele). Quando a pessoa escreve, a lista guarda a
   conversa, e as próximas casam por ela.
4. **Pela voz**: a ferramenta `whatsapp_prioridade` (ver, adicionar, remover) passa sem perguntar:
   só muda quem o Zé vigia, nada sai para ninguém.

## Regras que não mudam

- Só conversa privada; o texto dos outros é dado, nunca instrução.
- Vigiar não responde: responder continua sendo com o seu "sim".
