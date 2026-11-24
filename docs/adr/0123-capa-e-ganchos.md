# 0123 — A capa sobre o tema e o roteiro que resolve

- Data: 23/11/2026
- Status: **Aceito** (pedido de quem usa; vídeos de referência aprovados em 23/11/2026).
- Muda a capa do [ADR 0109](0109-publicar-reels.md), os formatos do
  [ADR 0113](0113-formato-ritmo-e-voz.md) e o convite do [ADR 0120](0120-convite-dos-videos.md).

## Contexto

A capa do Reels era um quadro do gancho, posto também como o quadro 0: pegava a frase no meio da
animação ("NA SUA", "Conferir extrato na mão é"). Os roteiros se repetiam: "lista" e "erro"
levavam ao "passo 1, 2, 3", e os ganchos eram perguntas genéricas. Quem usa pediu que o vídeo
agregue para o dono de negócio (e não tenha cara de anúncio), que a história termine com a
solução de quem fala, que o convite sirva a quem é de outro ramo (a marca é generalista) e que o
gancho seja imagem e frase de impacto juntas. A fala também passava do tempo pedido (o ritmo da
voz estava calibrado em 2,9 palavras por segundo; a voz atual fala 2,3).

## Decisão

1. **A capa é uma peça à parte, sobre o tema** (`zervis/video/capa.py`, a cena "capa" da página):
   o diretor escreve o tema como título (de 2 a 5 palavras: "Cobrança no automático"), o
   destaque, o objeto do tema (o ícone) e qual foto da marca é o retrato de quem fala. A peça:
   fundo escuro na cor da marca, título enorme à esquerda, o ícone num selo e o retrato fundido
   à direita (as bordas somem no fundo; sem recorte). Sem retrato, o título e o ícone ao centro.
   Vai ao Instagram como `cover_url`; o vídeo começa no seu primeiro quadro.
2. **O gancho:** 5 candidatos (`ganchos`), abre o mais forte; o primeiro quadro é imagem e frase
   juntas (o "gancho" com "foto": a foto enche a tela, véu escuro, a frase clara por cima). A
   imagem da primeira cena entra no primeiro instante. Pergunta genérica, saudação e "no fim eu
   te digo" estão proibidos.
3. **O formato "caso"** em quatro tempos: o problema (um personagem com nome, negócio e cidade, e
   a conta na tela com números de exemplo), a solução de quem fala ("a gente faria três coisas",
   cada uma mostrada funcionando), o resultado e a ponte (o mesmo problema em outros negócios).
   É exemplo: "a gente faria", nunca um cliente atendido; caso real só com o material.
4. **O vídeo agrega:** ensina algo que serve a quem nunca vai contratar (o mecanismo, a conta,
   o porquê), no tom de dono de negócio brasileiro, sem promessa vaga. O tema pode ser qualquer
   processo (atendimento, financeiro, fiscal, estoque, pessoas, gestão, pós-venda); os exemplos
   do diretor cobrem vários.
5. **O convite é a palavra do problema** ("comenta COBRANÇA"), não o ramo de quem assiste.
6. **Nada de passo a passo:** sai o formato "lista"; entram "caso", "cena", "contra" e
   "resultado"; no máximo duas cenas que enumeram (mais que isso, o roteiro volta ao diretor).
7. **Fotos livres sem gente nem arquivo histórico:** o domínio público do Commons é cheio de foto
   oficial de governo e de guerra; as categorias, o título e a descrição barram pessoas,
   governo, guerra e fotos antigas.
8. **O ritmo da voz** recalibrado para 2,3 palavras por segundo (a duração bate com a pedida).

## Consequências

- A capa custa uma foto a mais da página, em segundos.
- A resposta do diretor fica um pouco maior (os ganchos e a capa), na mesma chamada.
- Sem retrato nas fotos da marca, a capa sai só com o título e o ícone.
