# 0041 — Voz pelo ElevenLabs, opcional, com o Cadu de reserva

- Data: 27/10/2026
- Status: **Aceito** (pedido da pessoa em 27/10/2026: o Cadu às vezes pronuncia mal o português e
  ela quer o ElevenLabs como motor de voz opcional, como no LIGATIA).
- Complementa o [ADR 0012](0012-voz-piper-e-escuta-deepgram.md) e o
  [ADR 0013](0013-agpl-e-piper-dentro-do-ze.md) (o Cadu pelo Piper, dentro do Zé).

## Contexto

O Cadu (Piper `pt_BR-cadu-medium`) é local, grátis e rápido: a primeira frase sai em cerca de
130 ms. Mas ele erra a pronúncia de algumas palavras do português, e a pessoa nota isso na conversa.
O LIGATIA (o SaaS de voz da mesma pessoa) usa o ElevenLabs como uma das vozes do catálogo, pelo
plugin do LiveKit Agents, e é o que ela quer trazer para o Zé.

## Decisão

1. **O Cadu continua o padrão e a reserva.** O ElevenLabs só entra quando a pessoa cola a chave
   na página Voz. A chave é conferida listando as vozes da conta. Se ela vale, fica em
   `<config>/elevenlabs.key` (0600) e o Zé já passa a falar pelo ElevenLabs, com a primeira voz
   da lista e uma frase de amostra. Vozes que falam português vêm primeiro, e as masculinas antes
   das femininas. A escolha (motor e voz) fica em `<config>/voz.json`. Voltar ao Cadu é um clique.
2. **Modelo `eleven_v4_turbo`, `language_code` "pt", PCM a 24 kHz em streaming**
   (`/v1/text-to-speech/{voz}/stream`). O v4 Turbo é o recomendado para conversa em tempo real
   (cerca de 100 ms) e custa o mesmo por caractere que o Flash v2.5: US$ 0,04 por mil caracteres
   na tabela de 27/10/2026. O áudio volta no formato do Piper (float32, frase a frase). Por isso a
   fila, a interrupção ("Ei Zé" corta a fala), o anel e a voz pelo celular não mudam.
3. **Uma conexão aberta, aquecida enquanto o cérebro pensa.** O aperto de mão TLS até o
   ElevenLabs custaria centenas de milissegundos em toda primeira frase. A conexão abre quando o
   pedido vai ao cérebro e serve a todas as frases da resposta. Uma fala cortada no meio fecha a
   conexão, porque o resto da resposta não serve.
4. **Se falhar, o Cadu fala.** Sem crédito, chave revogada, voz apagada ou sem rede, a frase sai
   pelo Cadu e a Atividade registra o motivo (uma vez por motivo). Durante 60 s o Zé não tenta o
   ElevenLabs de novo, para não atrasar cada frase esperando a falha. Salvar no painel tenta na
   hora.
5. **Fica de fora:** o treino do "Ei Zé", que sintetiza amostras com o Cadu, e o atendimento por
   telefone (`zervis/atendimento`), que tem seu próprio caminho de voz.

## Consequências

- O texto de cada resposta falada vai ao ElevenLabs. O áudio do microfone, não: ele segue só para
  o Deepgram, como antes.
- Custo por caractere. A página Voz mostra quantos caracteres saíram pelo ElevenLabs no dia, e a
  latência de cada turno passa a registrar quem falou (`voz_por`), para comparar o Cadu e o
  ElevenLabs na mesma etapa "voz".
- A primeira frase depende da rede até os servidores do ElevenLabs. A medida real vem das
  latências do próprio Zé depois de a pessoa ligar.
