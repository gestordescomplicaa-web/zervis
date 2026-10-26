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

Depois, para ligar de novo, toque no ícone do Zé Voz.

## Como funciona
- **Modo chamado** (padrão): o Zé ouve o "Ei Zé" como no microfone do PC (a escolha "Ativação" da
  página Voz vale aqui também). O **botão do fone** (ou "Falar" na notificação) abre o pedido; de
  novo, envia.
- **Ao vivo**: cada frase é um pedido, como o "Ao vivo" do navegador.
- Com um fone Bluetooth, o microfone e a fala vão por ele (o modo de comunicação, como numa
  ligação). Com alguns fones, nesse modo o botão vira "atender/desligar" e não chega ao app: aí
  use o "Ei Zé" ou o Falar da notificação.
- Caiu a rede: o app tenta de novo sozinho (2 s, 5 s, 15 s, 30 s, 60 s).
- Segurança: o app não entra no painel. O pareamento dá uma chave só de voz (o Zé guarda apenas
  o resumo dela); remover o celular no painel corta a chave na hora.

## Compilar
A CI compila (`.github/workflows/app-voz.yml`): num PR, o APK fica como artefato; na master, vai
para a versão `app-voz`, no link acima. Para cada versão instalar por cima da anterior, a CI
assina sempre com a mesma chave, criada uma vez por quem mantém:

    uv run python android/criar-chave.py

Sem a chave, sai um APK de depuração: funciona, mas cada versão nova pede desinstalar a anterior.

Localmente, com o JDK 21 e o Android SDK: `cd android && gradle assembleDebug`.
