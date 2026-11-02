# 0050 — Mapas de verdade: o Zé diz o que mostrar, os contornos vêm de dados oficiais

- Data: 30/10/2026
- Status: **Em validação** (conferido no navegador de teste e com o cérebro de verdade; falta a
  Imersão real).

## Contexto

Pedido "monta o mapa do Brasil", o Zé fazia um esboço feio com peças do holograma (ADR 0048) ou
pontos soltos. Não era falta de modelo: o cérebro já é o Claude Opus 5.5. Nenhum modelo de
linguagem desenha o contorno de um país de memória com precisão, e o catálogo de cenas não tinha
contorno nenhum (o globo só aceita pontos).

## Decisão

1. **Bloco `mapa` nas cenas.** O Zé diz só *o quê*: `regiao` (brasil, uma região do Brasil, mundo,
   um continente ou um país), `destaques` pelo nome ou sigla (SP, Bahia, Nordeste, Argentina,
   EUA), com `valor` opcional para um mapa de calor, cidades em `pontos` com lat/lon e `ligar`
   para arcos. A tela desenha.
2. **Contornos reais, embutidos na Imersão.** `web/jarvis-mapas.json` (207 kB, 77 kB comprimido)
   tem os 27 estados pela malha do IBGE (dados públicos) e 200 países pelo Natural Earth 1:50m
   (domínio público), simplificados e em deltas de centésimos de grau. O arquivo sai de
   `zervis/imersivo/gerar_mapas.py`, que diz como baixar as fontes de novo. Não há rede na hora de
   mostrar.
3. **Nome não achado volta para o Zé.** A página confere os destaques; o que não existe no arquivo
   vem em `ignorados` ("mapa: Atlântida") no resultado da ferramenta, e a persona manda corrigir o
   nome em vez de dizer que apareceu.
4. **Dois jeitos de ver.** No painel (2D): os contornos aparecem com uma varredura, os destaques
   acendem pelo valor (escala de raiz quando os valores são muito desiguais, para não apagar todos
   menos um), os nomes que não cabem saem para o lado com linha guia, e a fonte dos contornos fica
   no rodapé. Com `relevo`, o mesmo mapa vira um objeto three.js num cartão de modelo: cada lugar
   sobe pela altura do valor, sobre uma mesa quadriculada, e a pinça gira. O relevo usa material
   sólido iluminado: o vidro holográfico transformava o país inteiro num clarão branco.
5. **Honestidade:** mapa com valores é gráfico (fonte ou ILUSTRATIVO, como os outros); sem
   valores, cita a fonte dos contornos.
6. **Correção junto:** o cartão de modelo inclinava o objeto para trás (`rx` negativo mostrava a
   mesa e o sistema solar por baixo). Agora os montados aparecem vistos de cima.

## Teste com o cérebro de verdade (30/10/2026)

Claude Opus 5.5, oito pedidos (mapa do Brasil, estados do Nordeste, população por estado, onde
fica o Paraguai, maiores cidades, Brasil em 3D, países que falam português, Europa com França e
Alemanha): os oito viraram blocos `mapa` com a região e os destaques certos, de 5 a 17 s, uns 50
mil tokens cada; todos os nomes foram achados no arquivo.

## Consequências

- Municípios, bairros e mapas de outros países por estado ficam de fora (o arquivo cresceria
  muito); entram como arquivos à parte, baixados sob demanda, se fizerem falta.
- Países muito pequenos (ilhotas abaixo de 0,02 grau²) não aparecem no mapa do mundo.

## Ajustes do uso real (30/10/2026)

- "Mostra o mapa do Nordeste" chegou a mostrar o mundo: a região escrita de outro jeito não era
  reconhecida. Agora `regiao` é lida por inteiro primeiro (Rio Grande do Norte é estado, Coreia
  do Sul é país), depois por continente, região do Brasil e "brasil" no meio da frase; o que não
  for reconhecido volta em `ignorados` como "mapa: regiao X".
- A região sem destaques acende sozinha (o Nordeste, a Bahia, a Argentina).
- `isolar` mostra só a região ou os destaques, sem o resto ("só o Nordeste, não o Brasil").
