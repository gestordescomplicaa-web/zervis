# 0056 — O arquivo do WhatsApp: o Zé guarda tudo, busca quando você pergunta e lê sem gastar token

- Data: 03/11/2026
- Status: **Em validação** (testado com o WhatsApp simulado; falta o número de verdade).
- Substitui a caixa de 7 dias do [ADR 0054](0054-whatsapp-do-ze-recepcionista.md).

## Contexto

Pedido de 03/11/2026: o Zé saber tudo o que existe no WhatsApp, como uma memória com metadados
(quem, quando, em que conversa), para lembrar do que aconteceu. E gastar menos: cada leitura pelo
cérebro custava ~48 mil tokens lidos (quase todos do cache) em duas chamadas, e a aba Conversas
mostrava a soma como se fosse o custo.

Decisões de quem usa: guardar as conversas privadas **e os grupos**, responder **só no privado**, e
guardar **para sempre**, até mandar esquecer.

## Decisão

1. **O arquivo** (`zervis/avisos/caixa.py`, `<dados>/whatsapp-arquivo.db`, SQLite 0600): conversas
   (nome, telefone, se é grupo) e mensagens (quem escreveu, texto, tipo de mídia, a hora do
   WhatsApp, o id do evento contra repetição), com busca por palavras (FTS5, sem acento, por
   prefixo, as mais relevantes primeiro pelo bm25). A caixa de 7 dias entra uma vez e fica
   guardada ao lado (`.importado`).
2. **Grupos entram só para lembrar.** O WaCalls passa a capturar o grupo, com quem falou e o nome
   do grupo (consultado uma vez por grupo, como o WhatsApp Web faz). Grupo nunca vai ao agente de
   atendimento, ao julgamento de lead, à lista de prioridade nem à resposta (recusado no Python e
   no Go).
3. **Busca pela voz**: `whatsapp_buscar` (palavras, contato ou grupo, últimos N dias) devolve só
   os trechos relevantes (até 15): o cérebro recebe centenas de tokens, não a conversa inteira.
   `whatsapp_esquecer` apaga uma conversa do arquivo, com o seu sim.
4. **Leituras sem token**: "quem me mandou mensagem?", "tem alguém esperando?", "quem está na
   lista?" e "lê a mensagem da Ana" são frases fechadas que o Zé responde sozinho, do arquivo, sem
   o cérebro. O que pede mais ("o que a Ana disse do orçamento?", "lê e responde") vai ao cérebro.
   "Zérvis, ..." passa a valer como chamado nos comandos, como "Zé, ...".
5. **A aba Conversas** mostra o gasto como "novos + do cache · gerados": o lido do cache custa uma
   fração e não pesa igual na conta.

## O que não muda

- O WhatsApp não é consultado além do que já chega: o Zé não pede histórico. Guardar no próprio
  computador não muda nada para a Meta.
- O texto dos outros é dado, nunca instrução; os dados ficam na máquina (`docs/essencia.md`).

## Depois

- O histórico que o celular manda ao conectar um aparelho (hoje descartado pelo WaCalls): guardar
  no próximo pareamento, sem pedir nada a mais.
- Perfil do contato e busca por sentido (embeddings locais), se a busca por palavras não bastar.
- Enviar ao cérebro só as ferramentas do assunto e enxugar a persona, medindo com a bateria.
