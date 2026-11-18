# 0103 — Áudio na conversa com o Zé pelo WhatsApp

- Data: 18/11/2026
- Status: **Aceito** (pedido de quem usa, 18/11/2026).
- Complementa o [ADR 0102](0102-conversa-pelo-whatsapp.md) (a conversa com o Zé pelo WhatsApp).
  Abre uma exceção à decisão de 13/08/2026 do WaCalls ("sem mídia": só texto, nunca o arquivo).

## Contexto

Pelo WhatsApp, quem usa fala com o Zé como fala com qualquer pessoa, e boa parte disso é áudio.
A conversa do ADR 0102 respondia aos áudios "Por enquanto, só mensagens de texto." O WaCalls
nunca baixa mídia: guarda só que houve um áudio, e isso protege as conversas de todos os outros
contatos.

## Decisão

1. **O WaCalls guarda a referência, não o arquivo.** De cada áudio recebido numa conversa
   privada fica, em memória, a referência que o próprio WhatsApp manda (o caminho e a chave do
   arquivo): no máximo 200, por 10 minutos, e cada uma vale um pedido só. Nada vai ao disco.
2. **O arquivo só é baixado quando o Zé pede** (`GET /api/sessions/{sid}/audio?evento=...`, com o
   token da subida), e a Central só pede o áudio do número autorizado a conversar com o Zé. O de
   qualquer outro contato expira sem nunca ter sido baixado. Áudio com mais de 10 minutos ou
   8 MB é recusado.
3. **A Central transcreve pelo Deepgram** (nova-3, pt-BR, os termos do Zé), com a chave já
   configurada para a escuta, numa thread fora do receptor. O texto vira o pedido, igual a uma
   mensagem escrita; o arquivo fica só na memória enquanto é transcrito.
4. **Quando não dá:** sem a chave do Deepgram, o Zé responde "Reconhecimento de fala não
   configurado. Envie em texto."; sem fala reconhecida ou com falha no download, "Áudio não
   reconhecido. Envie de novo ou em texto." Foto, vídeo, documento e figurinha recebem "Por
   enquanto, só mensagens de texto e áudio."

## Consequências

- Cada áudio gasta a transcrição do Deepgram (a conta de quem usa), além do modelo.
- A resposta segue em texto. Responder em áudio fica para depois, se fizer falta.
