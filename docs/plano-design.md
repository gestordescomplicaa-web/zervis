# Plano do design: a base e, depois, a identidade Zérvis

Data: 25/11/2026. Pedido de quem usa, depois da comparação com Hermes, OpenBot e Grok Bot (nota do
front hoje ≈ 6,3; meta ≈ 8). Este plano cobre a **base**; o redesenho só começa quando quem usa
disser "agora o design", e todo design é mostrado antes, em imagens tiradas no Chromium, para ser
aprovado. Só então vira código.

## O que não pode quebrar

- **As funções do painel.** O redesenho muda a aparência e a organização; as chamadas ao Zé, os
  botões e o que cada um faz continuam os mesmos.
- **A Imersão** (zona protegida). O Zé 3D, a abertura e o jeito como ele se apresenta funcionam
  exatamente como estão: `zervis/imersivo/` inteiro, `zervis/portal/imersao.py`,
  `modulos/imersao.js`, a seção Imersão do `index.html`, as regras `.imersao`, `.barra-imersao`
  e `.tela-holo` e a lógica de abrir, tela cheia e desligar. Nenhum PR do design toca nisso.
- **O app Zé Voz.** O canal de voz (as mensagens nos dois sentidos, o primeiro recado, o código de
  "outro aparelho assumiu"), o pareamento e o link do QR continuam iguais; o app instalado nos
  celulares não pode deixar de funcionar.
- **A tecnologia.** O painel continua em JavaScript (módulos do navegador, tipos conferidos pelo
  `tsc`), HTML e CSS, sem framework nem etapa de compilação: leve (o orçamento de 130 KB na
  abertura), com os testes de hoje valendo. A aparência de produto maduro vem das decisões de
  design, não da biblioteca.

## A rede de proteção (PR 1)

| Proteção | O que pega | Onde |
|---|---|---|
| Mapa de contratos | botão que sumiu, mudou de nome ou passou a pedir outra coisa ao Zé, em cada página; o menu e os controles de voz | `tests/test_painel_contratos.py`, `tests/painel_contratos.json` |
| Fotos de antes e depois | toda mudança visual, página por página, no computador e no celular | `uv run python -m tests.fotos_do_painel` |
| Trava da Imersão | qualquer mudança nos arquivos dela ou nos trechos do painel que a ligam | `tests/test_imersao_protegida.py`, `tests/imersao_protegida.json` |
| Combinado do app | o Zé e o app deixarem de falar a mesma língua (mensagens, pareamento, QR, estados) | `tests/test_protocolo_do_app.py` |

Já existiam: todas as páginas abrem num Chromium sem erro (`test_painel_no_navegador.py`), os
tipos do JavaScript, toda página no menu e no mapa do Zé (`test_mapa.py`), os 17 testes da
Imersão no `make check` e o APK compilado na CI a cada mudança em `android/`.

Mudança de propósito (um botão novo, um nome melhor, um PR da própria Imersão): as variáveis
`ZE_ATUALIZAR_CONTRATOS=1` e `ZE_ATUALIZAR_IMERSAO=1` regravam a referência, e a diferença fica à
vista no PR.

## A base (PRs 2 e 3), sem mudar nada do que se vê

- **PR 2: cores e medidas num lugar só.** Toda cor, tamanho de texto, espaçamento, canto e tempo
  de animação do painel vem das variáveis do `painel.css` (hoje há 26 lugares com o ciano escrito
  direto). Prova: as fotos antes e depois iguais. Um teste confere que o app (`cores.xml`) segue
  as cores do painel. As regras da Imersão ficam como estão.
- **PR 3: os componentes com nome.** Cartão, linha, campos, botões, interruptor, etiqueta, aviso,
  vazio, carregando e erro ganham nome e regra em `docs/design.md`; os estilos avulsos das páginas
  viram componentes; um teste impede página nova com cor ou estilo avulso. Prova: fotos iguais.

## Depois, quando quem usa disser "agora o design"

1. A referência visual da identidade Zérvis, em imagens do Chromium, para aprovar. **Feito em
   25/11/2026:** o protótipo foi aprovado (ADR 0132).
2. ~~Um interruptor "Visual novo / Visual atual"~~: trocado pela volta por PR (dois visuais em
   paralelo dobrariam o código e a chance de erro).
3. A barra do Zé (o anel com o estado e o que ele está fazendo, falar de qualquer página) e o menu
   por áreas (Conversa, Trabalho, Negócio, Casa, O Zé).
4. A Conversa como linha do tempo, com cartões que se resolvem nela (aprovar, publicar, ouvir), e
   o "precisa de você". **O "Precisa de você", o Início pela voz e o sino: ADR 0133.**
5. As páginas em lotes, das mais usadas às menos usadas; os Ajustes num lugar só, com busca.
   **O Marketing em abas, com os ajustes separados por assunto: ADR 0134.**
6. Tirar o interruptor.

A Imersão fica fora de todos eles.
