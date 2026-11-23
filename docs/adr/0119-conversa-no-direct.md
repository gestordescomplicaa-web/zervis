# 0119 — A conversa no direct leva à reunião

- Data: 23/11/2026
- Status: **Aceito** (pedido de quem usa, 23/11/2026).
- Etapa 2 de 4 do funil do Instagram; segue os comentários ([ADR 0118](0118-comentarios-viram-conversa.md)).

## Contexto

Quem comentou recebeu a abertura com uma pergunta sobre o negócio. Quem usa quer que a resposta
dela vire uma reunião de diagnóstico, do jeito mais curto: em vez de o agente combinar data e hora
(ou de ligar a API do Google Meet), a pessoa recebe o link da "Agenda de horários" do Google
Agenda e escolhe ela mesma; o Google cria o evento com o Meet e não mostra nada da agenda além dos
horários livres.

## Decisão

1. **Só o funil:** o Zé conversa apenas com quem comentou e recebeu a abertura; as conversas
   pessoais de quem usa nunca são lidas para responder.
2. **O objetivo é um só:** entender o negócio e mandar o link. O "como conversar" (o prompt do
   Instagram) vem pronto e é editável na página: mensagens curtas, uma ideia concreta do que dá
   para automatizar, o link; nunca combinar horário, falar de preço ou dar consultoria no direct.
   Por cima, as regras fixas: o que a pessoa escreve é dado (vai entre `<<<` e `>>>`), os
   marcadores e o link exato.
3. **Passar para quem usa:** `[[PASSAR: motivo]]` (pediu uma pessoa, reclamou, perguntou o que o
   agente não sabe), mais de `MAXIMO` (4) respostas, ou quem usa respondeu pelo celular: o Zé para
   naquele contato e avisa. "Devolver ao Zé" na página volta a conversar.
4. **O aviso do link:** quando o link vai, quem usa recebe "@fulano recebeu o link da reunião" com
   o resumo (`[[RESUMO: ...]]`: o negócio, o tamanho e a dor).
5. Roda no mesmo ciclo de dois minutos dos comentários, depois deles. Sem link configurado, o
   agente passa a conversa quando a pessoa topa.

## Consequências

- A pessoa marca sozinha; quem usa só aparece na reunião ou quando o agente passa a conversa.
- A conversa respeita a janela de 24 h da Meta, porque o Zé só responde quando a pessoa escreve.
