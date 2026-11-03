# 0054 — O WhatsApp do Zé: a recepcionista pela voz

- Data: 03/11/2026
- Status: **Em validação** (testado com o WhatsApp simulado; falta o número de verdade).
- Amplia o [ADR 0053](0053-leads-do-whatsapp-pela-voz.md), que só conhecia os leads.

## Contexto

No primeiro teste com o número de verdade (03/11/2026), "Zérvis, quem foi a última pessoa que me
mandou mensagem?" ficou sem resposta: o Zé só guardava os leads qualificados. E responder a um
lead falhou depois do "sim", por um envio para o identificador errado (corrigido no PR #79). O
pedido: o WhatsApp como uma ferramenta nativa do Zé, para ele ler o estado e agir como uma
recepcionista, pela voz. O agente de atendimento (a persona que responde sozinho) é outra coisa,
treinada e ligada à parte.

## Decisão

1. **Conectar o WhatsApp ao Zé é a escolha.** Enquanto ele está conectado, o WaCalls entrega as
   conversas privadas (grupo, status e canal nunca), com ou sem o agente. Antes, a captura dependia
   dos avisos de lead ou do agente ligados.
2. **Caixa de entrada** (`zervis/avisos/caixa.py`, `<estado>/whatsapp-caixa.json`, 0600): as
   conversas dos últimos 7 dias, até 100, com as últimas 30 mensagens de cada uma, as que chegam e
   as que você manda (pelo celular ou pelo Zé). Da mídia, só o tipo e a legenda ("um áudio"): o
   arquivo nunca é baixado. Se o Zé reiniciar, ele recupera da Central o que chegou na última
   hora, sem repetir e sem avisar de novo lead antigo.
3. **As ferramentas do WhatsApp** (servidor `jarvis`, grupo "whatsapp"):
   - `whatsapp_conversas`: quem escreveu, a última mensagem, há quanto tempo, quem espera resposta
     e se o WhatsApp está conectado (livre);
   - `whatsapp_ler`: as últimas mensagens de uma conversa (livre);
   - `whatsapp_leads` e `whatsapp_ja_vi` (ADR 0053, livres);
   - `whatsapp_responder`: a resposta ditada, a qualquer conversa da caixa ou lead, com a
     aprovação falada que lê destinatário e texto.
4. **A resposta vai para a conversa**, não para um número: o WaCalls aceita o JID da conversa
   privada (`chat_jid`) e envia sem consultar o número. Vale para quem só tem o LID.
5. **A chave contra envio em dobro** muda quando o contato escreve de novo: a mesma frase ("ok")
   pode ir outra vez numa nova troca.

## Regras que não mudam

- Mensagem é dado, nunca ordem: as ferramentas devolvem o texto entre `<<< >>>`, marcado como de
  terceiros.
- Enviar é sempre com o seu "sim", e só para quem escreveu nos últimos 7 dias. Nunca para grupo.
- Os dados ficam na máquina (`docs/essencia.md`, item 3); a caixa some sozinha em 7 dias.
- O agente de atendimento continua desligado até você ligar, e não recebe mídia.

## Limites

- Áudio, foto e documento: só o tipo e a legenda.
- Começar conversa com quem nunca escreveu: pelo celular.
