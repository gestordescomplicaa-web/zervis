# 0062 — O app de voz como uma ligação no viva-voz, e o eco pelo texto

- Data: 03/11/2026
- Status: **Em validação** (o APK compila na CI; falta o teste no celular, no volume alto).

## Contexto

Mesmo com o cancelador de eco no servidor (ADR 0051), o Zé ainda se ouvia pelo celular, e tanto
mais quanto mais alto o volume. Causa: no alto-falante do próprio celular, o app tocava a fala
como mídia (como música), fora do modo de ligação. O cancelador de eco do Android só trabalha no
modo de ligação, com a referência da saída; e o do servidor perde para a distorção do alto-falante
pequeno no volume alto e para o atraso que varia. O pedido: "Ei Zé" e o modo ao vivo funcionando
como uma chamada telefônica, para trabalhar sem as mãos (inclusive entre reuniões de venda).

## Decisão

1. **Tudo como ligação, menos a caixa Bluetooth sem microfone**: sem Bluetooth, o app entra no
   modo de comunicação com a saída no viva-voz (`setCommunicationDevice` no alto-falante, ou no
   fone com fio plugado; `setSpeakerphoneOn` no Android 11) e a fala como
   `USAGE_VOICE_COMMUNICATION`, como uma ligação do WhatsApp no viva-voz. O cancelamento de eco do
   aparelho, afinado para o alto-falante dele, tira a fala em qualquer volume. O fone Bluetooth com
   microfone segue como antes (ligação, por ele). A caixa Bluetooth só de som (A2DP) não entra em
   ligação: segue como mídia, com o eco no servidor.
2. **Supressão de ruído do Android** junto com o cancelamento de eco, na captura.
3. **O eco pelo texto** (`zervis/voz/eco_texto.py`): a última rede. A transcrição que repete um
   trecho seguido de 5 palavras ou mais do que o Zé disse nos últimos 20 s, e cobre quase toda a
   transcrição (80 %), é descartada antes de virar pedido, no celular, no navegador e no PC.
   Repetir poucas palavras do Zé ("sim, detalha os concorrentes") continua valendo.

## Consequências

- O volume da fala no celular passa a ser o volume de ligação (as teclas de volume com o Zé
  falando); a qualidade é a de uma ligação no viva-voz, com o processamento do aparelho.
- O cancelador do servidor continua ligado: no modo de ligação ele recebe um sinal já limpo.
