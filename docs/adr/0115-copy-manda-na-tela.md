# 0115 — A copy manda na tela: imagem real na palavra

- Data: 19/11/2026
- Status: **Aceito** (vídeo de referência aprovado por quem usa como base, 19/11/2026).
- Segue o estilo Editorial e a lista ([ADR 0114](0114-estilo-editorial-e-lista.md)).

## Contexto

Quem usa pediu que a fala seja a mãe da animação: cada coisa dita deve virar, na palavra, legenda
e imagem real do que é falado (um prédio dito vira um prédio na tela; uma marca citada, o logo
dela). Pediu também a paleta da marca no Editorial, consistência de layout e tipografia, e o fim
do "caos virando ordem", que se repetia em todo vídeo.

## Decisão

1. **Cena "visual"** (`web/visual.js`): de 1 a 4 batidas, cada uma com a palavra da fala e o que
   mostrar. "sequencia" troca a imagem num cartão grande, em corte seco, a cada palavra;
   "colagem" junta as imagens no grid, uma a uma, e a da vez pulsa. O item da lista também
   aceita imagem (o logo no lugar do ícone, a foto em cima) e o placar mostra o logo.
2. **De onde vêm as imagens** (`zervis/video/fotos.py`): `logo: <marca>` pelo Simple Icons (o
   SVG na cor da marca, só desenho; baixado só o que o vídeo usa), `busca: <palavras>` no
   Commons e o nome de uma foto da marca. Os pedidos saem em paralelo, até 12 buscas por
   vídeo; o mesmo pedido escrito de outro jeito é um só. O que não vier vira um ícone, escolhido
   pela palavra que é o objeto.
3. **O diretor:** "a copy é a mãe da animação": a maior parte das cenas é visual ou item com
   imagem; ícone, conexão e hub só quando não há coisa real para mostrar; o caos sai.
4. **Editorial na paleta da marca**, com um sistema só: a tinta escura da marca, os dois
   destaques, uma escala de tipo, a mesma borda e sombra em todos os cartões e um grid fixo
   (imagem em cima, placar no meio, legenda embaixo).

## Consequências

- Os logos são marcas registradas dos donos; o vídeo só mostra a marca que a fala cita.
- A foto livre ainda é escolhida pelo título, sem olhar a imagem; as fotos da marca são o caminho
  forte.
