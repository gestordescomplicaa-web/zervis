# 0097 — As ferramentas do cérebro sob demanda

- Data: 17/11/2026
- Status: **Em validação** (medido com as ferramentas e a persona reais; falta a semana de uso
  pelos registros de consumo).

## Contexto

O gasto da semana de 10 a 17/11/2026 foi de 33,6 milhões de tokens lidos em 390 respostas. As
conversas gravadas do cérebro mostraram de onde vem: cada chamada ao modelo leva uns 42 mil
tokens fixos, antes de qualquer conversa (eram ~6 mil em outubro), e um pedido com ferramentas
faz de 5 a 12 chamadas. Os resultados das ferramentas são pequenos (a busca de modelos 3D, a
maior, dá ~2 mil tokens com as prévias); o histórico de uma conversa nunca passou de 54 mil.

Os 42 mil são, sobretudo, a descrição das ~100 ferramentas do Zé, mandada inteira em toda
chamada. O Claude Code já tem a busca de ferramentas (`ToolSearch`): as que não estão à mão
ficam fora do contexto e o modelo as acha quando precisa. Ela não ligava no Zé porque a lista de
ferramentas embutidas (`cerebro.ferramentas`: WebSearch e WebFetch) não trazia o `ToolSearch`.

## Decisão

1. Com servidores MCP, o cérebro do Claude leva o `ToolSearch` nas embutidas e nas livres (achar
   uma ferramenta não muda nada; não passa pela pergunta falada nem conta como uso).
2. **As mais usadas ficam sempre à mão** (`anthropic/alwaysLoad` no `_meta` da ferramenta): até
   16, as mais usadas nos últimos 30 dias pelo registro de uso, completadas por uma lista padrão
   numa instalação nova. Sem isso, cada ferramenta pedia uma ida e volta a mais para ser achada.
   O SDK em Python não leva essa marca por ferramenta: a listagem do servidor é embrulhada para
   acrescentá-la (`zervis/cerebro/carga.py`); se a forma interna mudar, as ferramentas só ficam
   todas sob demanda, e o teste avisa.
3. A via rápida que bate no limite da conta descansa até a janela renovar (a hora vem do aviso de
   limite do Claude; sem ela, 15 minutos): em 12/11/2026 ela tentou 110 vezes seguidas, ~1 s
   perdido em cada pedido.

## Medição (17/11/2026)

| Caso | Tokens lidos | Tempo |
|---|---|---|
| 100 ferramentas falsas, todas carregadas (como era) | 78,7 mil | 3,8 a 6,0 s |
| As mesmas, todas sob demanda | 10,3 mil | ~5,1 s |
| As mesmas, as mais usadas à mão e o resto sob demanda | 7,6 mil | 3,8 a 4,1 s |
| Zé real (57 ferramentas da avaliação, persona), conversa simples: antes → depois | 33,7 → 23,5 mil | 0,9 → 1,1 s |
| Zé real, pedido com uma ferramenta (2 chamadas): antes → depois | 67,4 → 47,1 mil | 2,2 → 2,4 s |

## Consequências

- No Zé em uso (~100 ferramentas, ~42 mil fixos) a chamada deve cair para ~23 mil: perto de
  metade do gasto, com as mesmas ferramentas e a mesma qualidade. A confirmação vem dos
  registros de consumo (`consumo (claude): leu ...`) da semana seguinte.
- Uma ferramenta pouco usada leva uma ida e volta a mais (a busca) na primeira vez da conversa.
- O que sobra fixo é a persona (~7,7 mil) e as essenciais (~6,3 mil; a `tela_explicar` sozinha
  tem 3,2 mil): os próximos candidatos a enxugar.
- Pelo OmniRoute ou outro provedor, o Claude Code desliga a busca e carrega todas, como antes.
