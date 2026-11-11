# 0081 — A cena no ritmo da voz

- Data: 11/11/2026
- Status: **Aceita** (`tests/imersivo/test_ritmo.py`; falta a prova com a voz real).

## Contexto

As cenas do "explicar" (ADR 0047) andavam por um relógio próprio: cada passo ficava na tela o
tempo de ler a sua fala (62 ms por letra). A cena chega quando o cérebro chama `tela_explicar`,
antes de ele terminar de escrever a resposta, e a voz só começa depois. Com muita coisa para
mostrar, os blocos trocavam e a tela limpava enquanto o Zé ainda falava dos anteriores.

## Decisão

1. **A voz diz onde está.** A voz toca em pedaços (a primeira frase sozinha, o resto em blocos);
   ao começar cada um, ela passa o texto ao anel, que grava `state/fala.json` com o pedaço e até
   que caractere ele já foi dito (pela duração do áudio gerado; enquanto ele ainda chega, no
   mínimo a estimativa pelo tamanho do texto). O `GET /orb` o entrega enquanto o Zé fala.
2. **Cada passo espera a fala do próximo** (`jarvis-ritmo.js`). O primeiro passo aparece com a
   cena; os outros, quando a posição da voz passa o lugar onde a fala deles começa no que o Zé
   diz. A procura compara as primeiras palavras da fala (sem números, que a voz diz por
   extenso, e sem acentos); o último passo fica até a resposta acabar.
3. **Sem voz para seguir, o ritmo de antes.** Modo silencioso, uma voz que não informa o texto,
   nenhuma resposta em 30 s: o tempo de leitura. Uma fala que o Zé não disse como escreveu: pela
   quantidade que ele já falou. A resposta acabou e ainda há passos: o resto, rápido.
4. O `tela_explicar` diz ao cérebro que cada passo aparece quando a voz chega à fala dele.

## Consequências

- A apresentação "quem" e a abertura não mudam: a abertura já fala passo a passo (ADR 0078).
- Uma resposta que diga as frases em outra ordem ou com outras palavras anda pela quantidade
  falada, sem a precisão da frase.
