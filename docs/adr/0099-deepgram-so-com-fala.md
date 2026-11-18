# 0099 — No Live, o Deepgram só ouve quando há fala

- Data: 17/11/2026
- Status: **Aceito** (pedido de quem usa, 17/11/2026). Medir na semana seguinte as horas com o
  Deepgram aberto (`Live: Deepgram ouvindo` e `dormindo` no registro).
- Revê uma consequência do [ADR 0042](0042-modo-live-tempo-real.md): "o Deepgram recebe o áudio
  durante toda a conexão ao vivo".

## Contexto

Com o app do celular ou o navegador conectado no Ao vivo, a sessão do LiveKit Agents (1.8.9)
manda cada quadro do microfone ao transcritor, sem filtro de voz. De 10 a 17/11/2026 foram
35,4 horas de Live aberto, com duas sessões de 12 e 14 horas: o app esquecido conectado durante
a noite. O Deepgram cobra pelo áudio, e a documentação não diz se a conexão parada, só com o
sinal de vida (KeepAlive), também conta. O Silencioso não muda isso: ele vale para o PC, e o app
conectado continua conversando (decisão de 26/10/2026).

## Decisão

1. **O transcritor da sessão envolve o Deepgram** (`zervis/voz/deepgram_que_dorme.py`). Todo
   quadro passa pelo Silero, local e sem custo. A conexão com o Deepgram abre quando ele percebe
   voz e fecha depois de 2 minutos sem fala (`DORMIR_S`).
2. **A primeira palavra não se perde:** o segundo de áudio de antes da voz fica guardado e vai
   primeiro, enquanto a conexão abre.
3. **O resto do Live não muda:** o detector de voz da sessão, o fim de fala, a interrupção e os
   avisos falados pela sessão seguem iguais. Para o LiveKit, é o mesmo transcritor, às vezes
   calado.
4. Fechar a conexão, e não só parar de mandar áudio, porque não está claro se a conexão parada é
   cobrada.

## A prova (17/11/2026)

Com as peças reais (Silero, o detector, o Deepgram e uma frase gerada pelo Piper), fora do
serviço e com 3 s para dormir: com só silêncio, a conexão não abriu. Com a fala, abriu e
transcreveu "Que horas são agora?". Sem fala, fechou. Na segunda fala, reabriu e transcreveu a
frase inteira, sem perder o começo. No `make check`, `test_o_deepgram_so_ouve_quando_ha_fala`
faz o mesmo com peças falsas.

## Consequências

- Com a casa em silêncio, o Deepgram não recebe nada, mesmo com o app conectado a noite toda.
- A primeira fala depois de um silêncio longo espera a conexão abrir (algumas centenas de
  milissegundos) antes de a transcrição chegar; as falas seguintes, dentro dos 2 minutos, não.
- Barulho que o Silero toma por voz (uma TV alta) abre a conexão até 2 minutos depois de parar.
