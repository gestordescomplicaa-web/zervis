# 0057 — O Instagram do Zé, só leitura: perfil e métricas, analisados pela voz

- Data: 03/11/2026
- Status: **Em validação** (testado com a API da Meta simulada; falta a conta de verdade).

## Contexto

Pedido de 03/11/2026: o Zé ajudar a analisar o Instagram (o perfil, quantas publicações, qual post
rendeu mais visualizações), sem falar no Instagram. Não há conector oficial do Instagram para o
Claude: o MCP oficial da Meta cobre anúncios; os conectores do diretório são serviços de terceiros
(os dados passam por eles, e a maioria é paga). Há MCPs de código aberto sobre a API oficial, mas
com ferramentas de publicar e dezenas de descrições que pesariam em todo turno.

## Decisão

1. **Nativo e só leitura** (`zervis/redes/instagram.py`): só GET na API oficial (v26.0). Nada que
   publique, comente ou responda existe no código.
2. **Os dois logins da Meta**: o token do Login do Instagram (`IG…`, `graph.instagram.com`,
   renovado sozinho a cada semana) e o do Login do Facebook (`EAA…`, `graph.facebook.com`, a conta
   do Instagram achada pela Página). O painel aceita o que a pessoa colar: o token, uma URL com
   `access_token=` ou o JSON do Explorador.
3. **O token** fica em `<config>/instagram.key` (0600), nunca no registro.
4. **Métricas atuais**: por publicação, visualizações, alcance, curtidas, comentários, salvamentos,
   compartilhamentos e interações (e o tempo médio dos reels); da conta, alcance, visualizações,
   contas engajadas, interações, toques nos links e seguidores ganhos menos perdidos (até 30
   dias). As descontinuadas (`impressions`, `plays`) não são pedidas.
5. **Cache** em `<dados>/instagram-cache.json`: a lista por 1 hora, as métricas de post da última
   semana por 1 hora e as dos antigos por 1 dia; as que faltam são lidas em paralelo (8 por vez).
   Stories ficam de fora (expiram em 24 horas).
6. **A conta é feita no Zé** (`zervis/redes/analise.py`): ordenar, filtrar por tipo e período,
   somar e tirar a média. O cérebro recebe poucas linhas prontas, pelas ferramentas
   `instagram_perfil` e `instagram_posts` (livres: só leem).
7. **A página Atendimento vira "Redes sociais"**: WhatsApp, Instagram e Avisos primeiro; o agente
   de atendimento em uma seção à parte.

## Depois

- Comparar períodos ("este mês contra o passado") e o melhor horário de publicar.
- Criar conteúdo e agendar, quando decidido: escrever no Instagram é outra decisão (outro ADR).
