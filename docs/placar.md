# Placar do Zérvis

Versão 0.3.0. Gerado por `zervis placar` (plano de maturidade, Frente 3), só com
números agregados: nenhuma fala, resposta ou nome.

## Avaliação do cérebro

Rodada de 2026-11-09, claude:claude-opus-5-5, 103 cenários, 3x cada: **93%**.

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
| Recorte | Via rápida | 50 | 3,9 s | 27,9 s | 0 |
| Recorte | Cérebro completo | 230 | 4,0 s | 7,9 s | 0 |
| Recorte | Comando local | 47 | 2,0 s | 4,3 s | 0 |
| Ao vivo | Via rápida | 116 | 3,2 s | 36,9 s | 12 |
| Ao vivo | Cérebro completo | 370 | 3,8 s | 5,3 s | 216 |
| Ao vivo | Comando local | 19 | 12,2 s | 12,2 s | 0 |
