# Placar do Zérvis

Versão 0.5.1. Gerado por `zervis placar` (plano de maturidade, Frente 3), só com
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

| Fala | Caminho | Turnos | p50 | p95 | Falhas |
| --- | --- | --- | --- | --- | --- |
| Recorte | Via rápida | 21 | 3,4 s | 8,4 s | 1 |
| Recorte | Cérebro completo | 53 | 4,9 s | 6,5 s | 0 |
| Recorte | Comando local | 33 | 2,1 s | 2,3 s | 0 |
| Ao vivo | Via rápida | 102 | 2,6 s | 7,2 s | 3 |
| Ao vivo | Cérebro completo | 392 | 3,7 s | 6,1 s | 172 |
| Ao vivo | Comando local | 10 | 26,1 s | 45,3 s | 0 |
