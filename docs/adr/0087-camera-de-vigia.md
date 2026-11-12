# 0087 — Câmera de vigia: uma foto local por movimento

- Data: 12/11/2026
- Status: Aceita; validada com uma câmera iCSee de três lentes (X3-WE2Q)

## Contexto

O usuário quer que o Zé acompanhe o sensor de movimento da câmera Wi-Fi iCSee e guarde uma foto
com o horário. O Zé não fala, não envia avisos e não envia fotos sem um pedido. Nenhuma
credencial ou endereço IP entra no repositório.

Na câmera real, três coisas não estavam no plano:

- O alarme aos clientes da rede (`MsgtoNetEnable` em `Detect.MotionDetect`) vem desligado de
  fábrica. A câmera detecta, mas não avisa ninguém na rede local, e a assinatura de alarmes fica
  muda.
- O evento de pessoa se chama `appEventHumanDetectAlarm`, e não `MotionDetect`. Os nomes mudam
  com o firmware: `VideoMotion`, `MotionDetect`, `PIRAlarm`…
- A câmera tem três lentes (`ChannelNum: 3`), e cada alarme diz qual delas viu (`Channel`).

## Decisão

1. A câmera é acessada na rede local pelo protocolo DVRIP/Sofia, TCP 34567. O login usa o usuário
   e a senha cadastrados no painel; a senha só é transformada no hash exigido pelo protocolo para
   entrar. O cadastro fica em `camera.json`, na configuração XDG, com permissão 0600. A tela nunca
   recebe a senha de volta e o código não contém IP nem credenciais de quem usa.
2. O vigia mantém uma conexão, envia KeepAlive e assina os alarmes. Ao conectar, ele liga o
   `MsgtoNetEnable` de cada lente que estiver desligado e não muda nenhum outro campo da
   detecção. É a única configuração que o Zé grava na câmera.
3. Vale o evento cujo nome fala de movimento, pessoa ou PIR, com status `Start`. O `Stop` não faz
   nada. A foto é da lente que viu. O intervalo cadastrado (30 segundos por padrão) vale por
   lente, para que uma pessoa que passe de uma lente para outra saia nas duas. Um alarme que
   chega enquanto o Zé espera outra resposta da câmera fica guardado e é tratado em seguida.
4. A foto é pedida por OPSNAP (1560), no canal da lente. Se o firmware não entregar JPEG por essa via, o Zé tenta um
   quadro RTSP com o `ffmpeg` do sistema, se estiver instalado. A senha vai por um descritor
   anônimo, sem entrar nos argumentos do processo nem em arquivo temporário. Sem uma imagem
   válida, a operação falha com uma mensagem curta.
5. As fotos são gravadas em `<dados>/camera/fotos`, com diretório 0700 e arquivos 0600. O nome
   leva a data e hora do fuso de quem usa e, em câmera com mais de uma lente, a lente
   (`AAAAMMDD-HHMMSS-lente2.jpg`). A própria câmera grava a hora na imagem. Ficam as 500 mais
   recentes, e o painel mostra as 100 mais novas.
6. A ferramenta de voz lista fotos e pode tirar uma agora, uma por lente. Uma imagem só chega ao celular ou ao
   navegador quando o pedido da pessoa pede para vê-la; o painel permite consultar as fotos.
7. Não se tenta descobrir a senha por listas ou repetição de logins. Se a senha do aparelho foi
   esquecida, a ajuda da iCSee orienta restaurar pelo botão físico, reconfigurar o Wi-Fi e definir
   uma nova senha do dispositivo.

## Consequências

- A senha precisa ser a do aparelho, não a senha de acesso à conta iCSee.
- Depois de um login recusado, o vigia aguarda novo cadastro em vez de repetir tentativas.
- Algumas versões podem não aceitar OPSNAP ou alarmes de terceiros. O painel mostra o estado, e
  a captura RTSP depende de `ffmpeg` instalado.
- Fora o `MsgtoNetEnable`, a câmera não recebe comandos de movimento, PTZ, áudio ou
  configuração. O Zé só lê alarmes e imagens.
- Com a lente montada de cabeça para baixo, a foto sai assim também. Na câmera testada, as
  lentes extras aceitam o `PictureFlip`/`PictureMirror` do aparelho, mas ignoram (mesmo depois de
  reiniciar). Por isso o giro fica no Zé: o cadastro marca as lentes a girar ("Girar imagem
  180°"), e a foto dessas lentes é girada com o Pillow antes de ser guardada. O relógio que a
  câmera grava na imagem gira junto. Então o Zé escreve a hora de novo, legível, no alto à
  direita, e o relógio da câmera fica de ponta-cabeça embaixo.
