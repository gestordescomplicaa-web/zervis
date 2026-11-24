# 0131 — O app de voz com cara de produto: Início, Parear e Ajustes

- Data: 24/11/2026
- Status: **Aceito** (pedido de quem usa; referência visual aprovada antes do código).
- Ajusta o [ADR 0024](0024-voz-pelo-https.md) (o canal de voz ganha a mensagem `estado`).

## Contexto

O Zé Voz tinha uma janelinha de diálogo com os botões padrão do Android: sem as cores do painel,
com rótulos que mostravam o estado ("Ligada", "Ouvir: “Ei Zé”") e textos coloquiais ("Sem o
microfone, o Zé não ouve."). O app é a voz com a tela bloqueada, mas é também a primeira coisa
que quem instala vê.

## Decisão

1. **Três telas, com a identidade do painel** (`zervis/portal/web/painel.css`): fundo escuro com
   o brilho ciano, cartões de vidro, o ciano de destaque, interruptores e seletores no lugar dos
   botões que mostravam o estado. Tela cheia (não mais o diálogo), desviando das barras do
   sistema. Sem biblioteca nova: Java, o framework do Android e layouts em XML.
   - **Parear:** o logo, os três passos (painel, QR, permissões), o endereço e o código com o erro
     embaixo do campo.
   - **Início:** o Zé no centro com o estado em volta (`Orbe`), como o ícone do painel: respira
     pronto, ondas ouvindo (maiores com a voz), arco pensando, pulso falando, âmbar esperando o
     "sim", apagado sem conexão. Embaixo, por onde a fala sai e quem é o microfone, o seletor
     "Ei Zé | Ao vivo" e o botão que muda com o estado: Falar, Enviar, Conectar, Retomar, Tentar
     agora.
   - **Ajustes:** cartões Escuta de perto (com o nível do microfone e a marca do mínimo), Áudio
     (a saída sem fone ou o microfone do aparelho Bluetooth), App (versão e atualização; com
     versão nova, o botão vira o principal) e Conexão (Desconectar, em vermelho).
2. **O Zé manda o estado pelo canal de voz:** `{"tipo":"estado","estado":"ouvindo"}` (os valores
   da máquina de voz: ativo, ouvindo, pensando, falando, confirmando, inativo), só quando muda; a
   conexão nova recebe o atual logo. O navegador ignora. Sem ela (um Zé antigo), o app deduz o
   que sabe: o botão apertado, o pedido enviado (pensando, até 30 s) e a fala tocando no celular.
3. **Os ícones** saem do logo do painel e da Lucide que o repositório já traz, pelo
   `android/icones.py`; nada de imagem solta sem origem.
4. **Testar no emulador:** só a versão de depuração aceita `http://10.0.2.2` (um Zé de teste no
   computador); a publicada continua só com HTTPS.

## Consequências

- O app passa a ter duas telas de verdade; "Fechar" sai (o voltar do Android fecha) e
  "Desconectar" mora nos Ajustes. Desconectado, o Início mostra "Conectar".
- As notificações levam o macaco na cor do Zé e textos curtos e factuais ("Sem conexão. Nova
  tentativa em 5 s."); a foto em tela cheia tem "Fechar" no alto, o título e "Compartilhar"
  embaixo, desviando das barras do sistema.
