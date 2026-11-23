# 0121 — Fotos livres só as que dispensam o crédito

- Data: 23/11/2026
- Status: **Aceito** (pedido de quem usa, 23/11/2026).
- Muda o item 4 do [ADR 0112](0112-fotos-nos-videos.md) e o item 6 do
  [ADR 0114](0114-estilo-editorial-e-lista.md).

## Contexto

Desde o ADR 0114, o crédito das fotos livres do Commons ia só na legenda do Reels ("Fotos: Foto:
Fulano · CC BY-SA 4.0 · Wikimedia Commons; ..."). Um vídeo com nove fotos punha nove créditos no
fim da legenda, e quem usa não quer a lista de fontes no post. Quase todas eram CC BY ou CC BY-SA,
que exigem o crédito em algum lugar; a tela também não era opção (cara de rodapé técnico).

## Decisão

1. **Só entra a foto livre cuja licença dispensa o crédito:** o Commons diz isso por arquivo
   (`AttributionRequired` = `false`: domínio público, CC0). O resto da escolha não muda (as
   palavras do pedido no título, nunca foto de pessoa).
2. **Mais resultados por busca** (20, eram 8): numa amostra, uns 45% das fotos dispensavam o
   crédito.
3. **A legenda do Instagram não leva lista de fontes**, e o vídeo não leva crédito na tela. As
   fotos da marca, os logos (Simple Icons, CC0) e os prints de site já não pediam crédito.

## Consequências

- Menos fotos livres servem; sem uma que sirva, a cena vira o ícone do objeto, como antes. As
  fotos da marca continuam o caminho forte.
- A Imersão não muda: lá a foto mostra o crédito na tela, junto da imagem.
