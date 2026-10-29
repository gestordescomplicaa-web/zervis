# 0047 — Cenas que o Zé escreve: "me explica X" vira gráficos, ondas e 3D na Imersão

- Data: 29/10/2026
- Status: **Em validação** (na Imersão de teste; a pessoa aprova o visual antes do merge).

## Contexto

A apresentação do ADR 0046 mostra só o próprio Zé, com painéis feitos à mão. A pessoa quer que
ele explique qualquer assunto do mesmo jeito: "Zé, me explica X" e a tela se enche de gráficos,
efeitos, ondas e 3D animados, no estilo do laboratório do holograma. Quer também tirar o Núcleo
(o anel com os orbes), que fica para uma etapa própria.

## Decisão

1. **Um catálogo de blocos, não código gerado.** O Zé escreve a cena em JSON (`titulo` e
   `passos`, cada passo com `fala` e até quatro `blocos`), e a página desenha cada bloco com um
   renderizador já pronto (`jarvis-cenas.js`): titulo, numero, barras, linha, rosca, etapas,
   rede, onda, forma3d (esfera, toro, hélice, cubo, átomo, galáxia, terreno, neural, plexo),
   globo, comparar, lista e linha_tempo. O 3D é canvas 2D com projeção, sem novo contexto WebGL
   ao lado do Zé e do MediaPipe. Um modelo não escreve HTML nem script para a tela.
2. **A página não confia na cena.** `limpar()` corta textos e listas, descarta tipos que não
   conhece (devolvidos em `ignorados`) e limita a 10 passos e 16 blocos. A página monta o layout
   sozinha: um título e até quatro blocos por página, à direita do Zé; o que não cabe vira a
   página seguinte.
3. **Honestidade dos números.** Bloco com número leva `fonte` ou `ilustrativo`; sem nenhum dos
   dois, a tela marca ILUSTRATIVO. Esquemas (etapas, rede, onda, 3D, comparação, lista) dizem
   ESQUEMA. Assim uma explicação bonita nunca passa um número inventado por medido.
4. **Mesmo palco da apresentação.** Os blocos são os painéis do ADR 0046 (cartões do quadro, a
   mão pega e arremessa), com os mesmos feixes, a legenda e o Zé no canto. `jarvis-apresentacao.js`
   expõe o roteiro (`palco.roteiro`) e os dois usam o mesmo.
5. **Quem dispara:** a ferramenta `tela_explicar` (livre, como as outras da própria tela), que
   vira a ação `explicar` com a cena; a tecla E passa pelos exemplos (MCP, som, DNA, rede neural);
   `?cena=<exemplo>` abre um direto.

## Consequências

- A fala de cada passo é a legenda; o Zé diz as mesmas frases na resposta, e a página anda pelo
  tamanho do texto. Sincronizar com o áudio de verdade fica para depois.
- Um bloco novo é um renderizador e uma linha no esquema de `tela_explicar`; a descrição da
  ferramenta cresce com o catálogo, então ela fica curta.
- Arquivo novo da página entra na lista do servidor dos testes (`tests/imersivo/test_brain_navigation.py`).
