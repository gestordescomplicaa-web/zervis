# 0109 — Publicar os vídeos como Reels, e pedir vídeos de qualquer lugar

- Data: 18/11/2026
- Status: **Aceito** (pedido de quem usa, 18/11/2026).
- Etapas 2 e 3 dos vídeos ([ADR 0106](0106-videos-de-marketing.md) e
  [ADR 0107](0107-direcao-dos-videos.md)). Segue o caminho dos posts
  ([ADR 0093](0093-posts-do-instagram.md)) e a aprovação fora do WhatsApp
  ([ADR 0104](0104-aprovacao-no-painel.md)).

## Contexto

O Zé já criava os vídeos, mas não sabia postá-los: o cartão Vídeos não tinha "Publicar", o
publicador do Instagram só enviava imagens (foto e carrossel), e o cérebro não tinha ferramenta de
vídeo, então "faz um Reels sobre X e posta" pela voz, pela Conversa ou pelo WhatsApp não tinha
como acontecer.

## Decisão

1. **Publicar como Reels** (`instagram_publicar.publicar_reels`): o contêiner `REELS` com o link
   do MP4, a legenda que o diretor escreveu, `share_to_feed` e a capa no primeiro quadro (o Zé já
   põe a capa nele). O Zé espera a Meta processar (até 10 minutos, conferindo a cada 8 s), publica
   e guarda o link.
2. **O MP4 sai por um link público temporário** no endereço fixo do Zé, como as imagens dos posts:
   segredo longo, só aquele arquivo, aberto por 25 minutos e fechado logo depois. A rota passa a
   aceitar `.mp4` e a responder `HEAD` (quem baixa vídeo costuma conferir antes); o resto do painel
   continua sem responder `HEAD`.
3. **Publicar exige o "sim" de quem usa:** no painel, "Publicar no Instagram" e depois "Confirmar
   publicação"; pela voz, a pergunta "Vou publicar no Instagram o vídeo “...”. Posso?"; pelo
   WhatsApp, a aprovação fica pendente no painel. Só um vídeo pronto, de 3 a 90 s, com o Instagram
   conectado e o endereço fixo, pode ser publicado.
4. **Sem Reels em dobro:** um vídeo que ficou "publicando" porque o Zé parou no meio é conferido
   no perfil depois de 15 minutos. Saiu: vira "publicado", com o link. Não saiu: volta a pronto,
   com o aviso para conferir no Instagram antes de publicar de novo.
5. **Ferramentas do cérebro:** `marketing_videos` (lista, livre), `marketing_video_criar` (o tema
   ou o artigo e a duração; pede o "sim", como criar um post) e `marketing_video_publicar` (pede o
   "sim", com o título do vídeo na pergunta).

## Consequências

- "Cria um vídeo sobre X" funciona pela voz, pela Conversa e pelo WhatsApp; publicar, só depois de
  assistir e aprovar.
- A Meta limita publicações por conta (o erro vira "Limite de publicações do Instagram").
- Agendar a publicação e publicar em outras redes (TikTok, Shorts) ficam para depois.
