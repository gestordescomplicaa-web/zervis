# 0130 — Quem atende o número, a resposta automática e os avisos do que trabalha sozinho

- Data: 24/11/2026
- Status: **Aceito** (pedido de quem usa, depois do primeiro dia da prospecção de verdade).
- Ajusta o [ADR 0127](0127-prospeccao.md) (envio e resposta) e o [ADR 0029](0029-central-de-avisos.md)
  (a central de avisos passa a valer para a Prospecção e o Instagram).

## Contexto

O primeiro dia da prospecção, em 24/11/2026, mostrou quatro coisas:

1. **A saudação automática virou resposta.** A Dau e a Cavalcante "responderam" um minuto
   depois do envio, com a saudação do WhatsApp Business ("Bem-vindo(a) a DAU AUTOPEÇAS… me
   informa o modelo, ano e motor"). As duas viraram "Respondeu" e aviso de lead.
2. **A mensagem ao dono caiu na loja.** As duas saíram para o número do Google Maps, que é o
   atendimento da loja (o da Dau é a televenda). O celular da Receita não existia ou era fixo.
   Quem leu "Oi, Williams" foi quem atende.
3. **O "adianta uma" saiu por fora.** Pedido pela voz, o Zé mandou pelo `whatsapp_enviar` e
   descartou a empresa: o envio não ficou marcado nem contou no limite do dia.
4. **Os avisos ficavam só na tela.** A Prospecção e o Instagram escreviam uma linha na Conversa
   e mais nada: a pausa pelo freio, a Apify sem crédito e "@fulano quer falar com você no
   direct" não eram faladas, não esperavam na fila e não chegavam ao celular.

Junto, um número de preenchimento no cadastro da Receita, "(81) 0000-0001", entrava como telefone.

## Decisão

1. **A saudação é do código, pelo número que recebe.** O modelo escreve só o corpo, sem
   cumprimento; o Zé põe a abertura na hora do envio:
   - celular da Receita (o do contador já fica de fora): é do dono, "Oi, Carlos, tudo bem?";
   - o número do Google ou um fixo: é a loja, "Oi, tudo bem? Esta mensagem é para Carlos Lima,
     da JM Pneus. Se puder encaminhar, agradeço!" (nome e sobrenome, para quem atende saber
     quem é; sem artigo, porque o gênero não se sabe);
   - sem o dono: "para quem responde pela {empresa}".
   Se o primeiro número não tem WhatsApp e o envio cai no seguinte, a saudação muda junto. A
   mensagem editada por quem usa sai como está. A página mostra o texto que saiu. O "alcance" da
   nota passa a contar o celular da Receita; só o número da loja, no máximo 3.
2. **A resposta automática não é resposta.** Reconhecida pelas frases da saudação ("bem-vindo",
   "horário de atendimento", "digite 1", "em breve um atendente"…) ou, nos dois primeiros
   minutos, pelas de quem atende ("como podemos ajudar?"). O que chega no minuto seguinte é a
   continuação dela. Fica guardada na empresa ("automatica"), sem mudar o estado, sem aviso de
   lead e sem passar pela lista de prioridade. A pessoa que escreve depois vira "Respondeu",
   como antes.
3. **"Adianta uma" pela voz** (`prospeccao_enviar_agora`, com a aprovação falada): a primeira da
   fila sai já, sem esperar o horário sorteado, pelo mesmo caminho do ciclo. O limite do dia e o
   horário de envio continuam valendo. A descrição da ferramenta proíbe adiantar pelo
   `whatsapp_enviar`.
4. **Os avisos do que trabalha sozinho vão à central** (`notificar`): na tela, como antes;
   falados pelo modo de fala, com prioridade, e esperando na fila durável quando o Zé está
   ocupado. O urgente (alguém ou algo espera você) vai também ao seu WhatsApp, o número
   autorizado a falar com o Zé (ADR 0102), como o pedido de um grupo; o mesmo aviso, uma vez
   por hora.
   - Urgentes: a prospecção pausada pelo freio, o erro da Apify (chave, crédito, conexão),
     empresas esperando aprovação, "@fulano quer falar com você no direct" e "a conversa é sua
     agora".
   - Notificações: mensagem enviada, comentários respondidos, link da reunião entregue.
   A resposta de uma empresa contatada continua no caminho do lead (ADR 0053), com a
   notificação no app Zé Voz.
5. **Telefone de preenchimento fica de fora:** o número de assinante no Brasil começa de 2 a 9;
   começando por 0 ou 1, ou com todos os dígitos iguais, não é telefone.

## Consequências

- Na loja, a mensagem depende de quem atende encaminhar. Achar o celular do dono fora da Receita
  (site, Instagram) fica para depois.
- Uma saudação automática fora do padrão passa como resposta. O texto fica na empresa e
  "Respondeu" pode ser desfeito na página.
- O urgente no WhatsApp sai do número conectado para o seu número autorizado. Com a conversa com
  o Zé desligada ou sem número autorizado, fica na tela e na fala.
