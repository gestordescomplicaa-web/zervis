# Placar do Zérvis

Versão 0.5.2. Gerado por `zervis placar` (plano de maturidade, Frente 3), só com
números agregados: nenhuma fala, resposta ou nome.

## Avaliação do cérebro

Rodada de 2026-11-09, claude:claude-opus-5-5, 103 cenários, 3x cada: **93%**.

Rodada de uma versão anterior: a desta versão sai na próxima
`zervis avaliar --noturna`.

| Área | Nota |
| --- | --- |
| Voz e fala curta | 90% |
| Sessões de código | 97% |
| WhatsApp e atendimento | 93% |
| Ligações | 91% |
| Pesquisa | 89% |
| Memória | 92% |
| Aprovações | 92% |
| Injeção de prompt | 95% |

Gasto: 69,8 mil tokens por cenário, em média.

## Latência da voz

Do fim da fala ao primeiro som, nos últimos 7 dias de uso. Meta inicial: p95
abaixo de 2,5 s na via rápida.

| Fala | Caminho | Turnos | p50 | p95 | Modelo p50 | Modelo p95 | Falhas |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Recorte | Via rápida | 16 | 3,6 s | 5,1 s | 1,0 s | 2,9 s | 1 |
| Recorte | Cérebro completo | 54 | 5,0 s | 7,1 s | 11,8 s | 52,3 s | 1 |
| Recorte | Comando local | 4 | 2,0 s | 2,1 s | sem dado | sem dado | 0 |
| Ao vivo | Via rápida | 24 | 2,6 s | 3,8 s | 0,9 s | 1,4 s | 3 |
| Ao vivo | Cérebro completo | 66 | 4,1 s | 5,2 s | 18,1 s | 67,9 s | 1 |
| Ao vivo | Comando local | 11 | 1,1 s | 110,4 s | sem dado | sem dado | 0 |

Modelo: do pedido enviado à primeira palavra da resposta. No cérebro completo, sem
resposta em 3 s o Zé diz "Só um momento." e esse é o primeiro som.
