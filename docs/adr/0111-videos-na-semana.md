# 0111 — Vídeos na semana, sem repetir a receita

- Data: 18/11/2026
- Status: **Aceito** (pedido de quem usa, 18/11/2026).
- Segue os vídeos ([ADR 0106](0106-videos-de-marketing.md), [0107](0107-direcao-dos-videos.md),
  [0109](0109-publicar-reels.md), [0110](0110-edicao-dos-videos.md)) e o blog automático
  ([ADR 0092](0092-blog-automatico.md)).

## Contexto

Quem usa quer dar os temas uma vez e receber os vídeos durante a semana: o Zé cria, avisa no app,
a pessoa assiste e aprova, e só então o vídeo vai para o Instagram. A agenda só sabia escrever
artigos do blog. Feito no automático, o diretor também tende a repetir a receita que deu certo
(gancho, caos, conversa, conexão), e os vídeos ficariam todos com a mesma cara.

## Decisão

1. **Automação do tipo `video`** (`zervis/automacoes/jobs.py`): o texto é o JSON com até 10 temas
   curtos e a duração. Na hora, o Zé escolhe o tema (`Videos.proximo_tema`): o primeiro da lista
   que ainda não virou vídeo; sem ele, o artigo publicado mais novo que ainda não virou vídeo; sem
   ele, o diretor escolhe pela linha editorial do site, longe dos últimos vídeos.
2. **Aviso no app, publicação com aprovação:** o vídeo pronto avisa como qualquer vídeo ("está
   pronto para assistir em Marketing"). Publicar continua sendo um botão com confirmação no app ou
   o "sim" pela voz; nada vai ao Instagram sozinho.
3. **Memória do diretor:** o pedido ao modelo leva o título, o gancho e a receita (tipo,
   transição e fundo de cada cena) dos últimos 5 vídeos, com o pedido de fazer diferente. Se a
   sequência de tipos sair igual à de um deles, o roteiro volta uma vez para o diretor; na
   segunda, é aceito (o vídeo nunca falha por isso). Um ajuste pedido ("Refazer") segue a versão
   anterior, sem a memória.
4. **Variação do motor:** o lado de cada transição (carta, baralho, cubo, fatias, chicote) vem de
   uma semente do vídeo e da cena; a mesma transição não vira sempre para o mesmo lado.
5. **Onde agendar:** o cartão "Vídeos automáticos" em Marketing (quando, duração, temas um por
   linha) e a ferramenta `marketing_video_agendar` do cérebro (pede o "sim"). Pausar e remover
   ficam em Automações, como as outras.

## Consequências

- Cada vídeo agendado custa o mesmo que um pedido à mão (um plano do Opus, a voz e a montagem); a
  memória acrescenta poucas centenas de tokens ao pedido.
- Um tema da lista já feito é pulado (comparado sem acento nem maiúscula).
- O limite de texto das automações (600 caracteres) limita a lista a temas curtos; uma lista maior
  pede outra automação.
