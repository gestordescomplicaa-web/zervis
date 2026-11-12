# Zé Voz: o app de voz do Android

Fale com o Zé com o celular **bloqueado**, no bolso, pelo fone. O app não tem tela: fica uma
notificação "Zé conectado", com **Falar**, **Ao vivo / Usar "Ei Zé"** e **Desconectar**. O painel
continua no navegador; este app é só a voz, onde o navegador não chega (com a tela apagada, ele
corta o microfone).

Feito para uso pessoal, fora da Play Store: instala-se o `.apk` direto no celular.

## Instalar e parear
1. No celular, baixe o
   [ze-voz.apk](https://github.com/gestordescomplicaa-web/zervis/releases/download/app-voz/ze-voz.apk)
   e instale (o Android pede para permitir instalar de fonte desconhecida, uma vez).
2. No painel do Zé: **Voz → App de voz → Parear celular**. Precisa do acesso de qualquer lugar
   ativo, de preferência com o endereço fixo.
3. Aponte a **câmera** do celular para o QR: o Android abre o app, ele pareia e liga. Se a câmera
   não abrir o app, abra o Zé Voz e digite o endereço e o código que o painel mostra.
4. Permita o microfone e as notificações. Pronto: bloqueie a tela.

Depois, para ligar de novo, toque no ícone do Zé Voz. A tela que abre (também ao tocar na
notificação) mostra o estado da voz e os ajustes: o modo de ouvir, a escuta de perto, a saída sem
fone, o microfone do aparelho Bluetooth conectado e a atualização do app. Fechá-la não desliga a
voz; "Desconectar" desliga.

## Atualizar
Uma vez por dia, ao conectar, o app procura versão nova (o `versao.json` publicado junto do APK) e
avisa numa notificação. Na tela, "Procurar atualização" faz o mesmo na hora, e "Atualizar" baixa e
entrega ao instalador do Android: na primeira vez, ele pede para permitir que o Zé Voz instale
apps; depois, só a confirmação. Para isso, as versões precisam da mesma assinatura (abaixo).

## Como funciona
- **Modo chamado** (padrão): o Zé ouve o "Ei Zé" como no microfone do PC (a escolha "Ativação" da
  página Voz vale aqui também). O **botão do fone** (ou "Falar" na notificação) abre o pedido; de
  novo, envia.
- **Ao vivo**: cada frase é um pedido, como o "Ao vivo" do navegador.
- **Silencioso**: vale para o PC. Com o app conectado, o Zé ouve e responde pelo celular; os avisos
  seguem só na tela, como no Silencioso. Ao desconectar, o PC continua mudo.
- Com um fone Bluetooth com microfone, o microfone e a fala vão por ele (o modo de comunicação,
  como numa ligação). Com alguns fones, nesse modo o botão vira "atender/desligar" e não chega ao
  app: aí use o "Ei Zé" ou o Falar da notificação.
- Sem Bluetooth, no alto-falante do celular (ou no fone com fio), também como numa ligação, no
  viva-voz: o próprio Android tira o eco da fala dele, em qualquer volume, como numa ligação do
  WhatsApp no viva-voz (ADR 0062). O volume da fala é o volume de ligação (as teclas de volume,
  com o Zé falando).
- Numa caixa de som Bluetooth sem microfone, a fala sai como mídia, por onde o celular toca
  música, e o microfone é o do celular; o eco sai no servidor (ADR 0051). A troca vale na hora,
  ao conectar ou desconectar um aparelho.
- **Microfone do celular num aparelho com microfone** (a caixa de som com viva-voz, o fone): na
  tela, "Microfone: de <aparelho>" troca para "Microfone: do celular". A fala continua saindo pelo
  aparelho, como mídia, e a escolha fica guardada para ele (pelo nome); os outros seguem a sua.
  Com vários aparelhos Bluetooth conectados, vale o que o Android usa para o som naquele momento.
- **Escuta de perto** (ADR 0086, ligada por padrão): pelo microfone do celular, só passa quem fala
  junto dele, como numa ligação fora do viva-voz; a conversa da sala, a TV e a rua vão como
  silêncio. Com fone (Bluetooth ou com fio), passa tudo. Na tela, a barra mostra o nível do
  microfone ao vivo e o "Mínimo para ouvir" acerta o corte: fale a um palmo e deixe o mínimo
  abaixo do seu nível; quem está longe deve ficar abaixo dele.
- **Saída da voz** sem fone: "Alto-falante" (padrão) ou "Fone da orelha", com o celular no ouvido.
- **Imagens** (ADR 0086): "me manda uma foto da impressão" e a foto da câmera da impressora chega
  numa notificação; tocar abre inteira. Os avisos da impressora com foto também. As fotos ficam no
  cache do app (as 10 mais novas).
- **Uma voz por vez:** se outro aparelho (o navegador, outro celular) conectar a voz, este mostra
  "Voz em uso em outro aparelho" e não reconecta sozinho; "Retomar" na notificação traz a voz de
  volta para ele.
- O app liga o cancelamento de eco e o de ruído do Android (quando o celular tem). E o Zé descarta
  a transcrição que for um trecho do que ele acabou de dizer (5 palavras ou mais seguidas): o eco
  que escapar não vira pedido. Ao vivo, numa caixa Bluetooth alta, o fone ainda é melhor.
- Ao fim de cada fala, o microfone espera a saída terminar de tocar (na caixa Bluetooth, o atraso
  passa de meio segundo) antes de voltar a valer: sem isso, na conversa contínua, o Zé ouvia o
  final da própria fala como um pedido. Durante a fala, o "Ei Zé" continua interrompendo.
- Caiu a rede: o app tenta de novo sozinho (2 s, 5 s, 15 s, 30 s, 60 s).
- **Leads do WhatsApp** (ADR 0053): com o WhatsApp conectado ao Zé, cada lead qualificado que
  espera resposta vira uma notificação, com o nome e a mensagem. Ela toca de novo a cada lembrete
  (10 em 10 minutos, até 1 hora) e some quando você responde. **Ouvir** pede ao Zé a mensagem
  falada (vale no Silencioso), **Abrir no WhatsApp** abre a conversa e **Já vi** para os
  lembretes; arrastar para o lado também. Na tela bloqueada aparece só "Mensagem importante no
  WhatsApp". Quem está na lista de prioridade do Zé, e quem respondeu ao que ele mandou por
  você, também aparece aqui (ADR 0055). O celular recebe enquanto o app está conectado.
- Segurança: o app não entra no painel. O pareamento dá uma chave só de voz (o Zé guarda apenas
  o resumo dela); remover o celular no painel corta a chave na hora.

## Compilar
A CI compila (`.github/workflows/app-voz.yml`): num PR, o APK fica como artefato; na master, vai
para a versão `app-voz`, no link acima. Para cada versão instalar por cima da anterior, a CI
assina sempre com a mesma chave, criada uma vez por quem mantém:

    uv run python android/criar-chave.py

Sem a chave, sai (e é publicado) um APK de depuração: funciona, mas cada versão nova pede
desinstalar a anterior. Ao criar a chave, reinstale uma vez; daí em diante as versões entram por cima.

Localmente, com o JDK 21 e o Android SDK: `cd android && gradle testDebugUnitTest assembleDebug`.
