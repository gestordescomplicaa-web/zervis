# 0101 — O vídeo ao vivo da câmera no painel

- Data: 18/11/2026
- Status: **Aceito** (pedido de quem usa, 18/11/2026). Validado na câmera iCSee X3-WE2Q.
- Complementa o [ADR 0087](0087-camera-de-vigia.md) (fotos por movimento) e o
  [ADR 0088](0088-conversa-pela-camera.md) (conversa pela câmera).

## Contexto

A leitura da câmera em 17/11/2026, só de leitura, mostrou o que ela entrega na rede local: em
cada uma das 3 lentes, um fluxo principal (H.265, 1280 × 720, 12 quadros por segundo) e um leve
(H.265, 640 × 360), os dois com o áudio do microfone (G.711 A-law, 8 kHz), pelo RTSP (porta
554, autenticação Digest). A página web dela (porta 80) depende de um plugin antigo e não mostra
vídeo num navegador de hoje. O Zé só guardava fotos.

A mesma leitura achou um defeito: a foto de reserva por RTSP passava ao ffmpeg uma lista de
protocolos sem `rtp`, e o ffmpeg recusava o fluxo. A reserva nunca tinha funcionado.

## Decisão

1. **A página Câmera ganha o "Ao vivo":** um botão por lente, a qualidade e Parar. No PC, a
   qualidade alta (720p); de outro aparelho, a leve (360p), que pesa menos na rede de fora.
2. **O ffmpeg do sistema converte o H.265 em MJPEG** (`zervis/camera_ao_vivo.py`), que qualquer
   navegador mostra num `<img>`. A senha vai ao ffmpeg por um descritor anônimo, como na foto, e
   o RTSP vai por TCP (`option rtsp_transport tcp` no manifesto), porque no Wi-Fi o UDP perde
   pacotes. A lente marcada para girar sai girada.
3. **Só enquanto alguém assiste:** cada pessoa tem o seu ffmpeg, que termina quando ela sai da
   página ou esconde a janela. No máximo 3 ao mesmo tempo.
4. **A rota é uma transmissão do painel** (`/fluxo/camera/ao-vivo?lente=N&qualidade=alta|leve`),
   para quem já entrou: abre num `<img>`, que não manda o token da API, então vale o cookie
   (`SameSite=Strict`), como a Imersão (ADR 0100).
5. **A foto de reserva** usa o mesmo endereço RTSP e a lista de protocolos com `rtp`.

## A prova (18/11/2026)

Na câmera de verdade: lente 1 em qualidade alta, 1280 × 720, cerca de 13 quadros por segundo, o
primeiro em 2,1 s e uns 104 KB por quadro; lente 2 em qualidade leve, 640 × 360, cerca de 13
quadros por segundo e uns 27 KB por quadro. A foto de reserva por RTSP saiu em 1280 × 720, em
2,4 s.

## Consequências

- Exige o `ffmpeg` instalado ("Instale o ffmpeg para ver ao vivo.").
- Na qualidade alta, cerca de 1,4 MB por segundo por pessoa assistindo: bom na rede de casa,
  pesado pela rede de fora (por isso a leve fora do PC).
- O relógio que a câmera grava na imagem fica de ponta-cabeça na lente girada; nas fotos, o Zé
  reescreve a hora, no vídeo ainda não.
- O áudio do fluxo fica de fora (`-an`): ouvir o microfone continua só na conversa que quem usa
  abre (ADR 0088).
