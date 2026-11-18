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
2. **O vídeo de cada lente vem pelo DVRIP** (`OPMonitor`: reservar com 1413, começar com 1410,
   o vídeo chega em 1412), como no app iCSee. Revisto em 18/11/2026: a primeira versão usava o
   RTSP, e nesta câmera o RTSP traz só a lente 1, qualquer que seja o canal pedido; as lentes 2
   e 3 mostravam a 1. O Zé separa o H.265 do fluxo de mídia da Xiongmai (`camera.Midia`) e o
   entrega ao ffmpeg pela entrada padrão; a senha não passa pelo ffmpeg.
3. **O ffmpeg do sistema converte o H.265 em MJPEG** (`zervis/camera_ao_vivo.py`), que qualquer
   navegador mostra num `<img>`. A lente marcada para girar sai girada.
4. **Só enquanto alguém assiste:** cada vídeo aberto tem a sua conexão e o seu ffmpeg, que
   terminam quando a pessoa sai da página ou esconde a janela. No máximo 6 ao mesmo tempo (as 3
   lentes em dois aparelhos); a câmera aceita 10 conexões. "Todas" mostra as lentes lado a lado.
5. **A rota é uma transmissão do painel** (`/fluxo/camera/ao-vivo?lente=N&qualidade=alta|leve`),
   para quem já entrou: abre num `<img>`, que não manda o token da API, então vale o cookie
   (`SameSite=Strict`), como a Imersão (ADR 0100).
6. **A foto de reserva** pelo RTSP usa a lista de protocolos com `rtp`, por TCP (`option
   rtsp_transport tcp` no manifesto do ffmpeg). Ela vale para a lente 1, a única que o RTSP traz.

## A prova (18/11/2026)

Na câmera de verdade, pelo DVRIP (18/11/2026): as 3 lentes em 1280 × 720 (alta) e 640 × 360
(leve), cerca de 12 quadros por segundo, o primeiro quadro entre 0,7 e 3,6 s (espera o quadro-chave
da câmera), e as três imagens distintas. No Chromium, as 3 lentes ao mesmo tempo; ao fechar, as 3
conexões e os 3 ffmpeg terminaram. A foto de reserva por RTSP saiu em 1280 × 720, em 2,4 s.

## Consequências

- Exige o `ffmpeg` instalado ("Instale o ffmpeg para ver ao vivo.").
- Na lente 3 desta câmera, a imagem sai espelhada, nas fotos e no vídeo: ela precisa só de virar
  de cabeça para baixo, e "Girar 180°" vira e espelha. Fica para uma opção "Espelhar".
- Na qualidade alta, cerca de 1,4 MB por segundo por vídeo aberto: bom na rede de casa,
  pesado pela rede de fora (por isso a leve fora do PC).
- O relógio que a câmera grava na imagem fica de ponta-cabeça na lente girada; nas fotos, o Zé
  reescreve a hora, no vídeo ainda não.
- O áudio do fluxo fica de fora (`-an`): ouvir o microfone continua só na conversa que quem usa
  abre (ADR 0088).
