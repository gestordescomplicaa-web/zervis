"""Os vídeos do Zé (ADR 0106): Reels explicativos com a marca de quem usa, narrados pela voz do Zé.

O modelo escreve só o roteiro (as cenas e as falas, num formato fechado); o Zé faz o resto aqui,
sem nada de fora além do Chromium e do FFmpeg da máquina:

- `roteiro`: o pedido ao modelo e a conferência do que ele devolve;
- `estilos`: o visual e as cenas de cada estilo (o "Zérvis" vem junto; os de quem usa ficam em
  `<config>/video/estilos/<nome>/`);
- `narracao`: a voz, fala por fala, cada uma numa batida;
- `trilha`: a música composta em código, abaixando sob a voz;
- `captura` e `montagem`: os quadros no Chromium, em paralelo, e o MP4 no FFmpeg;
- `videos`: os vídeos de Marketing (criar, refazer, descartar), em segundo plano.
"""
