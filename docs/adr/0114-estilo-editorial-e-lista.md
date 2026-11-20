# 0114 — O estilo Editorial e a lista que evolui

- Data: 18/11/2026
- Status: **Aceito** (pedido de quem usa, a partir de um Reels de referência, 18/11/2026).
- Segue o formato e o ritmo ([ADR 0113](0113-formato-ritmo-e-voz.md)).

## Contexto

Quem usa mandou um Reels de referência (uma lista de 16 ferramentas). Analisado quadro a quadro, o
que ele tem e os nossos não: o que fica de uma cena para a outra (um placar de selos que acende e
um cartão que só troca o conteúdo), a legenda como identidade (serifa em caixa alta, palavra por
palavra, a palavra-chave em itálico vermelho), um visual claro de revista e a chamada "comenta X".

## Decisão

1. **Camadas no motor** (`Ze.camadas`): o que atravessa as cenas é desenhado a cada quadro, por
   cima delas.
2. **Cena "item"** (`web/lista.js`): o cartão do item (o ícone, a categoria, o número, a caixa do
   "sobre", o nome e um valor que conta). Itens seguidos são o mesmo cartão: o plano dá a eles o
   fundo do primeiro e nenhuma transição, e o motor não mexe no cartão entre dois itens.
3. **O placar:** com três itens ou mais, um selo por item (as iniciais) acende quando o item
   chega, com o contador "3/8".
4. **Fecho "comenta":** "Comenta “PALAVRA”", com a caixa do perfil e o botão de seguir.
5. **Estilo "Editorial"** (`estilos/editorial/`): parte do Zérvis (as peças de todas as cenas) e
   troca a paleta por papel bege, cartões brancos, preto, vermelho e amarelo; a legenda em
   Instrument Serif (o estilo pode ter uma fonte de legenda). O tom pede listas e o fecho comenta.
6. O crédito da foto livre sai da tela e fica só na legenda do post (a licença aceita).

## Consequências

- Quem usa escolhe o estilo no cartão Vídeos; o Zérvis segue o padrão.
- O apresentador em cena (parte grande da referência) espera o recurso de editar um vídeo gravado.
