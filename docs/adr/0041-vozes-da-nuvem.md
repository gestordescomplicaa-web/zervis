# 0041 — Vozes da nuvem (ElevenLabs e Fish Audio), opcionais, com o Cadu de reserva

- Data: 27/10/2026
- Status: **Aceito** (pedido da pessoa em 27/10/2026: o Cadu às vezes pronuncia mal o português e
  ela quer o ElevenLabs e o Fish Audio como motores de voz opcionais, como no LIGATIA).
- Complementa o [ADR 0012](0012-voz-piper-e-escuta-deepgram.md) e o
  [ADR 0013](0013-agpl-e-piper-dentro-do-ze.md) (o Cadu pelo Piper, dentro do Zé).

## Contexto

O Cadu (Piper `pt_BR-cadu-medium`) é local, grátis e rápido: a primeira frase sai em cerca de
130 ms. Mas ele erra a pronúncia de algumas palavras do português, e a pessoa nota isso na conversa.
O LIGATIA (o SaaS de voz da mesma pessoa) tem as duas vozes no catálogo, pelos plugins do LiveKit
Agents: o Fish Audio (padrão dele, com `latency_mode="low"`) e o ElevenLabs.

## Decisão

1. **O Cadu continua o padrão e a reserva.** Uma voz da nuvem só entra quando a pessoa cola a
   chave na página Voz. Se a chave vale, fica em `<config>/<provedor>.key` (0600) e o Zé já passa a
   falar por ele, com a primeira voz da lista e uma frase de amostra. A escolha (o motor e a voz
   de cada provedor) fica em `<config>/voz.json`. Trocar de motor ou voltar ao Cadu é um clique,
   e cada provedor lembra a sua voz.
2. **ElevenLabs:** modelo `eleven_v4_turbo`, `language_code` "pt", PCM a 24 kHz em streaming
   (`/v1/text-to-speech/{voz}/stream`). O v4 Turbo é o recomendado para conversa em tempo real
   (cerca de 100 ms) e custa o mesmo que o Flash v2.5: US$ 0,04 por mil caracteres na tabela de
   27/10/2026. A chave é conferida listando as vozes da conta. As que falam português vêm
   primeiro, e as masculinas antes das femininas.
3. **Fish Audio:** modelo S2.1 Pro (83 idiomas, português incluído), PCM a 44,1 kHz,
   `latency` "low" como no LIGATIA (`POST /v1/tts`). A chave é conferida pelo saldo de API
   (`/wallet/self/api-credit`, que é separado do crédito da plataforma). Com saldo, o Zé usa o
   `s2.1-pro`. Sem saldo, usa o `s2.1-pro-free`, grátis dentro do uso justo do Fish, e a tela diz
   qual está em uso. Na lista aparecem as vozes da pessoa e as 20 mais usadas em português da
   biblioteca. Qualquer outra voz entra colando o link dela (`fish.audio/m/<id>`).
4. **O mesmo motor para os dois** (`zervis/voz/nuvem.py`): o áudio volta no formato do Piper
   (float32, frase a frase). Por isso a fila, a interrupção ("Ei Zé" corta a fala), o anel e a voz
   pelo celular não mudam. Uma conexão fica aberta e é aquecida enquanto o cérebro pensa, para a
   primeira frase não pagar o aperto de mão TLS. Uma fala cortada no meio fecha a conexão, porque o
   resto da resposta não serve. Um provedor novo é um módulo com o mesmo contrato.
5. **Se falhar, o Cadu fala.** Sem crédito, chave revogada, voz apagada ou sem rede, a frase sai
   pelo Cadu e a Atividade registra o motivo (uma vez por motivo). Durante 60 s o Zé não tenta a
   nuvem de novo, para não atrasar cada frase esperando a falha. Salvar no painel tenta na hora.
6. **Fica de fora:** o treino do "Ei Zé", que sintetiza amostras com o Cadu, e o atendimento por
   telefone (`zervis/atendimento`), que tem seu próprio caminho de voz.

## Consequências

- O texto de cada resposta falada vai ao provedor escolhido. O áudio do microfone, não: ele segue
  só para o Deepgram, como antes.
- Custo por caractere, ou grátis no S2.1 Pro Free dentro do uso justo. A página Voz mostra os
  caracteres do dia e, no Fish, o saldo de API. A latência de cada turno passa a registrar quem
  falou (`voz_por`), para comparar o Cadu e a nuvem na mesma etapa "voz".
- O modelo do Fish é decidido pelo saldo quando a chave é salva. Quem coloca saldo depois salva a
  chave de novo para passar ao S2.1 Pro.
- A primeira frase depende da rede até o provedor. A medida real vem das latências do próprio Zé
  depois de a pessoa ligar.
