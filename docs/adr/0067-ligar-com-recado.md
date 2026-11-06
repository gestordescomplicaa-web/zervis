# 0067 — O Zé liga para dar um recado seu, agora ou agendado, e conta como foi

- Data: 06/11/2026
- Status: **Em validação** (testado com o WaCalls, a voz e o modelo simulados; falta a primeira
  ligação real).

## Contexto

Pedido de 06/11/2026: "Zé, liga para a Ana e diz isso e aquilo", como um recado de caixa postal,
com o "sim" antes; ou "às 17h liga para o João e diz para comprar o pão". O Zé tem de fazer a
ponta inteira: ligar, dar o recado e avisar se deu certo. E escolher a voz das ligações: o Cadu
(local) ou a voz do Zé (Fish Audio, hoje), para comparar.

O WaCalls já faz ligações de saída (`POST /api/sessions/<id>/calls`) e publica o estado delas
(`call-status`: tocando, atendida; `call-ended`, com o motivo: recusou, não atendeu, ocupado).

## Decisão

1. **O pedido** (`whatsapp_ligar`): o número (a agenda dá o do contato, ADR da agenda), o nome, o
   recado como foi pedido e, se houver, `quando`. Pede o "sim" com tudo isso: "Vou ligar agora
   para a Ana, no número 81 9…, com o recado: … Ligo?" ou "Vou agendar uma ligação hoje às 17:00
   para…". Agendada, vira uma automação do tipo `ligacao`, com a aprovação já dada.
2. **A ligação** (`Central.fazer_ligacao`): confere qual variante do número (com ou sem o nono
   dígito) está no WhatsApp, o que também prepara o identificador que a oferta precisa, e liga.
   Enquanto toca, o modelo escreve a primeira fala ("Oi, Ana! Aqui é o Zé, assistente do Fulano.
   …", sem inventar nada além do recado) e a voz a sintetiza: quando atendem, ela sai na hora.
   Depois, o recado vira conversa curta: repetir, tirar uma dúvida só com o que está no recado,
   ouvir uma resposta e se despedir (`[[DESLIGAR]]`), em até 3 minutos.
3. **O resultado** (`ligacao_feita`): atendeu e ouviu o recado (com o resumo do que a pessoa
   disse), recusou, estava em outra ligação, não atendeu em 45 s ou não saiu (o número fora do
   WhatsApp, por exemplo). O Zé avisa falando ("Fulano, liguei para a Ana e dei o seu recado.
   Ela disse que…"), na linha do tempo e na Atividade, e a ligação fica guardada como "feita".
4. **A voz das ligações** (página Atendimento, "Voz nas ligações"): **Local** (o Cadu, gerado
   no computador) ou **Voz do Zé** (a escolhida na página Voz, com o Cadu de reserva se o
   provedor falhar). Vale para as ligações que o agente atende e para as que o Zé faz.

## Consequências

- O que o Zé diz numa ligação de recado não entra no histórico do agente com aquele contato.
- Com a voz da nuvem, cada frase espera a síntese inteira antes de tocar: um pouco mais de
  silêncio entre a fala da pessoa e a resposta. A abertura sai pronta, sintetizada enquanto toca.
- Uma ligação por vez: um pedido durante outra é recusado com o motivo.
