# 0094 — As métricas do site, só leitura: o Search Console e o Google Analytics

- Data: 16/11/2026
- Status: **Em validação**: testado com o Google simulado (a chave, o Search Console, o GA4 e o
  Admin do GA4); falta a primeira leitura com a conta de verdade.

## Contexto

Quem usa quer saber se o site e o blog estão funcionando: quantas pessoas visitaram, quais artigos
foram lidos, se o site aparece no Google e quantos clicaram no WhatsApp. O Zé já cuida do site
(ADR 0091) e lê o Instagram (ADR 0057), mas não lia nenhum número do site.

As opções:

- **Vercel Web Analytics**: a hospedagem mais comum dos sites que o Zé cuida, mas não tem uma API
  aberta para ler os números; só exporta (os *drains*) no plano pago.
- **Google Search Console**: já existe para quem indexou o site, sem nada no código, e responde o
  "como as pessoas me acham no Google". API oficial, gratuita e com escopo só de leitura.
- **Google Analytics 4**: visitas, páginas, tempo de leitura, origem e cliques para fora (a
  "medição otimizada" do GA4 registra o clique em `wa.me` sem código a mais). API oficial,
  gratuita e só de leitura. Pede uma etiqueta no site.
- **Umami ou Plausible no próprio servidor**: sem cookies e com os dados em casa, mas é mais um
  serviço para manter. Fica para quando alguém pedir.

## Decisão

1. **Search Console e GA4, nativos e só leitura** (`zervis/metricas_site.py`): o escopo pedido ao
   Google é `webmasters.readonly` e `analytics.readonly`. Nada no código escreve no Google.
2. **Uma conta de serviço do Google Cloud de quem usa**: uma chave serve às duas fontes, não vence
   e não passa por tela de login. A pessoa libera o e-mail da conta no Search Console (usuário
   restrito) e no GA4 (leitor). O guia está em `docs/metricas-site.md`.
3. **A chave** fica em `<config>/google-metricas.json` (0600), só com o e-mail e a chave privada;
   nunca no registro nem no log. O Zé confere a chave no Google antes de guardar. A assinatura vai
   sempre para `oauth2.googleapis.com`, nunca para o `token_uri` da chave, e os pedidos só saem
   para os quatro endereços do Google.
4. **O site se declara** no `zervis.json` (`metricas`): o domínio, o começo das páginas do blog e,
   se quiser, a propriedade do GA4. Sem domínio, vale o único site que a conta vê no Search
   Console; sem propriedade, a única propriedade do GA4 que a conta vê (pela API Admin).
5. **A conta é feita no Zé**: os totais do período e as linhas do topo (buscas, páginas, origens,
   cliques para fora), em cache por 30 minutos. O cérebro recebe poucas linhas prontas, pelas
   ferramentas `site_google` e `site_visitas` (livres: só leem). Contam como entrada de fora: as
   buscas são o que estranhos digitaram, e qualquer um pode mandar página falsa ao GA4.
6. **Em Marketing**, o cartão "Métricas do site" mostra os últimos 28 dias das duas fontes, cada
   uma com o seu erro, sem derrubar a outra. A página não espera o Google: o cartão chega depois.

## Consequências

- O site precisa da etiqueta do GA4 para haver visitas a ler; o Search Console já tem os dados.
- O GA4 usa cookies: a política de privacidade do site precisa dizer isso (a do site de quem pediu
  já diz).
- Os números do GA4 dos últimos dias são parciais, e os do Search Console chegam com 2 ou 3 dias
  de atraso; o texto não esconde isso, mas também não avisa.
- Depois: comparar períodos ("este mês contra o passado"), um resumo semanal falado e usar as
  buscas para sugerir os próximos temas do blog.
