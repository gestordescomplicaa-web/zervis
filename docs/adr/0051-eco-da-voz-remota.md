# 0051 — O eco da voz remota sai no servidor

- Data: 30/10/2026
- Status: **Em validação** (provado em bancada; falta a caixa de som de verdade).

## Contexto

No Live pelo app do celular, com o Zé numa caixa de som, ele ouve a própria voz: só funciona com
fone de ouvido ou falando muito perto do celular. O app já liga o `AcousticEchoCanceler` do
Android, mas ele só cancela o que toca no modo de ligação, e a fala sai como mídia (no modo de
ligação, ela iria para o fone da orelha). Uma caixa Bluetooth sem microfone nem entra nesse modo.
Redução de ruído não resolve: a voz do Zé não é ruído.

## Decisão

1. **O eco sai no servidor**, onde o Zé sabe exatamente o que falou. `zervis/transporte/eco.py`
   usa o cancelador do WebRTC (AEC3, o do Google Meet), que já vem no SDK do LiveKit, com
   supressão de ruído e filtro de graves. Vale para o app e para o navegador, sem atualizar o APK.
2. **Tempo da fala no aparelho.** Cada pedaço mandado é marcado para quando deve tocar lá (depois
   do anterior, ou na chegada se a fala atrasou); cada quadro de 10 ms do microfone puxa a
   referência do seu instante. "Parar" descarta o que não tocou.
3. **Atraso longo medido.** O AEC3 acha sozinho até uns 400 ms. A caixa Bluetooth mais a rede
   pode passar disso: a cada segundo de fala, uma correlação cruzada com fase (GCC-PHAT) dos
   últimos 3 s mede o atraso; com duas medidas que concordam e um pico claro, a referência é
   atrasada e sobram 150 ms para o AEC3.
4. **Sem o WebRTC** (instalação sem o SDK), a voz passa como antes.

## Bancada (30/10/2026)

Fala do Zé (Cadu) com eco de sala, atraso de 150 a 900 ms, rede oscilando 30 ms, e uma pessoa
falando por cima: uns 20 dB de eco a menos em todos os casos; o atraso medido bateu (450 → 306,
700 → 554, 900 → 764 ms aplicados). Transcrito pelo Deepgram: o microfone bruto, com 700 ms,
virou a frase do Zé; depois do cancelador, sobrou só "zé para me mostra só pernambuco agora".
Custo: 1,1% de um núcleo.

## Consequências

- Com o eco fora, o Live pode seguir ouvindo enquanto o Zé fala (interromper pela voz), também na
  caixa de som.
- Falta a prova na caixa real. Se sobrar eco, o próximo passo é o app pôr a fala no modo de
  ligação pelo alto-falante (o cancelador do próprio Android) quando não houver fone.
