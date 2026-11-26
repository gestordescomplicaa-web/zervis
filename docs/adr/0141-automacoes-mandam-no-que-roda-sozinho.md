# 0141 — As Automações mandam no que roda sozinho, e cada uma se edita

- Data: 25/11/2026
- Status: **Aceito** (pedido de quem usa, 25/11/2026).
- Traz o "publicar sozinho" do [ADR 0126](0126-publicar-sozinho.md) (o PR #251 ficou parado e
  nunca chegou à master) e tira do Marketing os cartões de agendar dos ADRs
  [0092](0092-blog-automatico.md), [0111](0111-videos-na-semana.md) e 0126.

## Contexto

Em 25/11/2026 quem usa pediu pela voz: "agende automações de criação de vídeos, Reels, e
publique automaticamente segunda, quarta e sexta". O Zé respondeu que "o sistema não deixa
publicar sozinho" e não agendou nada: a opção estava no PR #251, sem mesclar.

O Marketing também agendava por conta própria: os cartões "Artigos automáticos" e "Vídeos
automáticos" (e o "Carrosséis automáticos" do #251) criavam a automação, mas só listavam a
agenda. Mudar a hora, os dias, os temas ou o "publicar sozinho" de uma que já existia não dava,
nem no painel nem pela voz: só remover e criar de novo. Duas portas para a mesma coisa, e
nenhuma completa.

## Decisão

1. **Uma porta só: as Automações.** Tudo o que roda na agenda (lembrete, pergunta, ligação,
   artigo, vídeo, carrossel) é uma automação, e a página Automações é onde se vê e se muda. Os
   cartões de agendar saem do Marketing, com as rotas `marketing/agendar`,
   `marketing/video/agendar` e `marketing/post/agendar`.
2. **Criar é pela voz**, pela ferramenta do tipo (`automacao_lembrete`, `automacao_pergunta`,
   `marketing_agendar`, `marketing_video_agendar`, `marketing_post_agendar`, a ligação). Com
   "publicar sozinho" pedido, a ferramenta recebe `publicar: true` e a confirmação falada diz
   "cada um vai ao ar sozinho, assim que ficar pronto, sem te perguntar" (ADR 0126).
3. **Editar, no painel ou pela voz.** Cada automação abre em "Editar": o nome; quando (dias da
   semana e hora, uma vez com data e hora, ou um intervalo); e o que o tipo tem (o texto do
   lembrete e da pergunta, o tema do artigo, os temas e a duração do vídeo, os temas do
   carrossel, o "publicar sozinho" dos três de marketing). Pela voz, `automacao_editar` muda só
   o que foi pedido, com a confirmação falada. A ligação muda só o nome e quando: o número e o
   recado foram aprovados pela voz quando ela foi agendada.
4. **A agenda dita como gente** na lista e na voz ("Segunda, quarta e sexta, 9h", "A cada 3
   dias"), não o cron. Um cron que o formulário não monta aparece como "Agenda personalizada" e
   fica como está até alguém escolher outra.
5. **"a cada 3d" passa a valer.** As ferramentas de marketing sempre sugeriram dias no
   intervalo, e a agenda só aceitava horas, minutos e segundos.

## Consequências

- O Marketing mostra o trabalho (os pedidos, os vídeos, os posts); a agenda dele está nas
  Automações, com o "Publica sozinho" à vista em cada uma.
- Mudar a hora de uma automação recalcula a próxima vez; uma pausada continua pausada.
- Sem a voz, não se cria automação nova pelo painel. Se fizer falta, o botão entra na página
  Automações, não de volta no Marketing.
