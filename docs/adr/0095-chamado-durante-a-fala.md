# 0095 — O "Ei Zé" que é a própria voz do Zé não interrompe

- Data: 17/11/2026
- Status: **Aceita** (medido no headset de quem usa; teste em `tests/test_eco_da_fala.py`).

## Contexto

Enquanto o Zé fala, o detector do "Ei Zé" fica ligado: é assim que a pessoa o interrompe. Em
17/11/2026, numa resposta de notícias, ele se interrompeu sozinho duas vezes, com o bipe, e parou
de falar. Os trechos guardados de cada chamado mostraram a causa: nos dois disparos falsos havia
2 s de voz contínua num tom de uns 300 Hz (a voz do Zé); nos chamados de quem usa, meio segundo
de voz a uns 128 Hz.

O fone e o microfone eram o mesmo headset, na cabeça. Medido depois: a fala do Zé chega ao
microfone 140 ms depois de tocar, a -32 dBFS, acima do volume mínimo do chamado (-31 dBFS,
calibrado pela voz de quem usa). A redução de ruído não ajuda, porque tira o ruído constante e
deixa a voz passar.

O cancelador de eco que o Zé já tem para a voz remota (ADR 0051, AEC3 do WebRTC) foi testado
na mesma gravação e tirou só 1 dB. A cadeia do microfone fecha um portão de ruído entre as
falas, e o caminho fone-microfone deixa de ser linear, que é o que o AEC3 modela.

## Decisão

1. A voz guarda o que tocou nos últimos 10 s, no relógio monotônico (`zervis/voz/eco.py`).
2. Quando o chamado dispara, o Zé compara os 3 s do microfone com o que tocou, em energia por
   faixa de frequência a cada 20 ms, no melhor atraso (até 1,6 s):
   - **semelhança**: a correlação no último 1,2 s (onde está o chamado);
   - **sobra**: quanto o microfone passa do que se espera ouvir, que é o eco ou, nas pausas, o
     ruído de fundo do próprio microfone.
3. Semelhança de 0,80 ou mais e sobra abaixo de 11,5 dB: é eco. O chamado é ignorado, fica no
   registro ("chamado ignorado: a própria voz do Zé no microfone") e o trecho é guardado com
   `-ignorado`, como os chamados baixos demais.
4. Sem nada tocado no período, nada muda.

## Medição (17/11/2026)

19 s de fala do Zé tocados no headset (Dell WH1022, na cabeça) e gravados pelo microfone, com
62 chamados simulados:

| Caso | Barrado como eco |
|---|---|
| Só o eco da fala | 62 de 62 |
| Chamado de quem usa por cima, no volume normal | 0 de 62 |
| O mesmo, 6 dB mais baixo (o limite do volume mínimo) | 3 de 62 |
| Só o eco, com chiado de -50 dBFS no microfone | 62 de 62 |

## Consequências

- O Zé não se interrompe mais com a própria voz, com fone, headset ou caixa de som.
- Um chamado muito baixo por cima da fala do Zé pode ser tomado por eco (3 em 62 no limite do
  volume mínimo): repetir o "Ei Zé" mais alto resolve.
- O resultado do AEC3 neste headset põe em dúvida a validação de bancada da ADR 0051, que usou
  eco linear simulado: falta a prova com o microfone de verdade.
