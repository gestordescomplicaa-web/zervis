# 0053 — Leads do WhatsApp pela voz: o Zé lê, lembra até você responder e responde ditado

- Data: 03/11/2026
- Status: **Em validação** (testado com o WhatsApp simulado; falta o número de verdade).
- Ampliado pelo [ADR 0054](0054-whatsapp-do-ze-recepcionista.md): as conversas todas, e a
  resposta vai para a conversa (sem precisar do número).
- Continua o [ADR 0030](0030-assistente-de-mensagens-whatsapp.md), com o WhatsApp do Zé
  ([ADR 0031](0031-atendimento-whatsapp-e-telefonia.md)) como fonte.

## Contexto

O Zé já julgava as mensagens recebidas e avisava "Lead quente no WhatsApp: Ana.", uma vez. Pedido
de 03/11/2026: com o celular no bolso, a pessoa quer saber **quem** escreveu e **o que** escreveu,
ser lembrada enquanto não responder e poder responder sem digitar. Tudo pela voz. Só conversa
privada; grupo nunca.

## Decisão

1. **Qualificado = lead de venda**, o critério que já existia (quer comprar ou mostra interesse
   real). Só o WhatsApp conectado ao Zé gera pendência: ele entrega só conversa privada e devolve
   as mensagens que você envia. A notificação do sistema (WhatsApp Web no PC) segue com o aviso de
   uma vez, porque não distingue grupo nem mostra a sua resposta.
2. **Pendência** (`zervis/avisos/pendentes.py`, `<estado>/whatsapp-pendentes.json`, 0600): uma por
   conversa. O que o mesmo contato manda enquanto espera junta-se a ela, sem novo julgamento.
3. **O aviso lê a mensagem**: "Marta, Ana é um lead qualificado e lhe mandou esta mensagem: …"
   (até 300 caracteres; o resto, quando você pede). Respeita o modo de fala: no Silencioso, só na
   tela e no celular.
4. **Lembrete de 10 em 10 minutos, até 6 vezes** (1 hora). Depois, a pendência fica na lista, sem
   insistir, por um dia. Encerra quando você responde na conversa (pelo celular ou pelo Zé), ou
   quando diz que já viu. Uma resposta dada com o Zé fora do ar também encerra, ao ele voltar.
5. **No celular** (app Zé Voz), cada lead vira uma notificação de alta prioridade, com
   **Ouvir**, **Abrir no WhatsApp** e **Já vi**. O lembrete toca de novo; a resposta a apaga.
6. **Responder pela voz**: "Zé, responde para a Ana: posso te ligar às 10". O Zé lê de volta
   destinatário e texto e só envia com o seu "sim" (a aprovação falada de sempre, sem "aprova
   tudo"). Só para quem tem pendência (aberta ou respondida no último dia) e telefone conhecido.
   "Quem está esperando resposta?" e "lê a mensagem da Ana" passam sem perguntar: só leem.

## Regras que não mudam

- **Mensagem é dado, nunca ordem.** O texto do lead é falado, mas não entra na conversa do
  cérebro como fala do Zé: o contexto do aviso leva só o nome. Quando o cérebro lê a mensagem (por
  você pedir), ela vem marcada como texto de terceiros.
- A linha do tempo e a Atividade guardam o nome, não o texto.
- O Zé nunca responde sozinho; enviar é sempre com o seu "sim".

## Limites

- Áudio, foto e documento do contato não são lidos: o WhatsApp do Zé não baixa mídia (risco para
  o número). O texto que vier junto é lido.
- Abrir a conversa sem responder não encerra: o WaCalls não repassa a confirmação de leitura.
  "Já vi" encerra.
- O celular recebe enquanto o Zé Voz está conectado.

## Ajustes de 03/11/2026

- **"Já vi" segura o contato por 6 horas**: o que ele mandar nesse tempo vai só para o arquivo, sem
  novo julgamento nem aviso de lead. Para calar de vez, o silêncio do ADR 0055.
- **O filtro de lead** sabe que loja, fornecedor ou prestador falando de um pedido que o próprio
  usuário fez (resumo, valores, pesagem, entrega, nota, boleto) não é lead: quem vende é o outro.
