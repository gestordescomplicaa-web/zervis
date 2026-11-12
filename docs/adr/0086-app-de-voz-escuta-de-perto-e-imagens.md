# 0086 — O app de voz: escuta de perto, imagens no celular e uma voz por vez sem briga

- Data: 12/11/2026
- Status: **Em validação** (testes de unidade da escuta de perto na CI do app e do envio da imagem
  no `make check`; falta a prova no celular: a sala com conversa e TV, e a foto da A1 chegando).

## Contexto

Três problemas do app Zé Voz (`android/`), vistos no uso:

1. **Ele ouvia tudo.** Com o celular na mesa, a conversa da sala, a TV e a rua viravam pedidos. O
   pedido de quem usa: o Zé só ouve quem fala junto do microfone, como numa ligação fora do
   viva-voz, ou pelo fone. O cancelamento de ruído do Android limpa o fundo constante (ventilador),
   mas não a voz de outra pessoa: para ele, voz é o que deve passar.
2. **A foto da impressora não chegava.** "Me manda uma foto da impressão" tirava a foto, o cérebro
   olhava e descrevia, mas a imagem não aparecia em lugar nenhum. As fotos dos avisos (erro,
   primeira camada, fim) ficavam só na pasta do Zé. O WhatsApp não serve: o número conectado é o
   de quem usa, e uma mensagem para si mesmo não toca.
3. **Dois aparelhos se derrubavam.** O Zé ouve uma voz por vez: a nova assume e a anterior é
   fechada. O app via o fechamento como queda de rede e reconectava em 2 s, derrubando o outro.

## Decisão

1. **Escuta de perto** (`android/.../Proximidade.java`), ligada por padrão. A voz a um palmo do
   microfone chega dezenas de vezes mais forte que a voz de quem está a dois metros; o app mede o
   nível em blocos de 20 ms e manda como silêncio o que fica abaixo do mínimo. Abre com 40 ms
   seguidos acima (um estalo não abre) e segura 600 ms depois da última voz, para pausas e sílabas
   fracas não serem cortadas. Vale só no microfone do próprio celular: com fone (Bluetooth ou com
   fio), o microfone já está na boca. O mínimo se acerta na tela, com o nível do microfone ao vivo.
   O áudio continua indo (zerado), para o Zé seguir com o ritmo de 80 ms de sempre.
2. **Saída no fone da orelha**, opcional, sem fone: o celular no ouvido, como uma ligação comum.
3. **Imagens para quem fala** (`VozNavegador.imagem`): a mensagem `{"tipo":"imagem"}`, com o JPEG
   em base64, no mesmo canal da voz. No app, vira notificação com a foto (tocar abre inteira); no
   navegador, abre sobre o painel. `impressora_foto` manda a foto a quem pede e diz ao cérebro onde
   ela apareceu; os avisos do vigia com foto (ADR 0085) também vão. Sem ninguém conectado de outro
   aparelho, nada é enviado: quem fala está no PC.
4. **O fechamento com motivo** (código 4001): o aparelho que perdeu a voz para outro não reconecta
   sozinho. O app mostra "Voz em uso em outro aparelho" e o botão "Retomar"; o painel, o aviso.

## Consequências

- O app precisa ser atualizado (a versão nova sai na CI ao mesclar).
- Falar de longe com o celular na mesa deixa de funcionar com a escuta de perto ligada: é o que
  foi pedido. Quem quiser o contrário desliga na tela do app.
- A foto vai pelo túnel inteira (umas centenas de KB) uma vez por pedido; o limite é 4 MB.
- O nível depende do microfone de cada celular: o padrão (30) vale para a voz a um palmo; a tela
  mostra o nível para acertar.
