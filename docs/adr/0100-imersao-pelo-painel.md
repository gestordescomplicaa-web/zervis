# 0100 — A Imersão pelo painel: o Zé e os cards de qualquer aparelho

- Data: 17/11/2026
- Status: **Aceito** (pedido de quem usa, 17/11/2026: "pelo menos o Zé animado, falando e
  animando os cards", na VPS). Falta a prova numa VPS de verdade.
- Complementa o [ADR 0014](0014-imersivo-dentro-do-ze.md) e o
  [ADR 0019](0019-autorizacao-http-do-imersivo.md), sem mudar a autorização do palco.

## Contexto

A aba Imersão abria o palco em `http://127.0.0.1:8794`. Do próprio PC, funciona. De outro
aparelho, esse endereço é o do próprio aparelho: com o Zé numa VPS, o palco não carregava, e o
painel mostrava só a imagem fixa do holograma. O servidor do palco aceita só o próprio PC
(ADR 0019), de propósito.

O que anima o Zé não depende do PC: o estado, o humor, a expressão, a onda da voz e a fala
vêm dos arquivos de estado que o Zé escreve, e os cards chegam pela fila de comandos do palco.
Só a câmera e as mãos são da máquina.

## Decisão

1. **O painel repassa o palco em `/imersao/`** (`zervis/portal/imersao.py`), só para quem já
   entrou com a senha. O pedido chega ao palco como se fosse do PC: o `Host` do palco, sem
   `Origin`, cookie nem o endereço de quem pediu. O token do palco continua exigido; ele vem na
   página, como antes. A resposta só abre dentro do próprio painel (`frame-ancestors 'self'`).
2. **O que mexe na máquina do Zé não passa:** a câmera (`/camera/`) e gravar a calibração das
   mãos (`POST /maos/`). Ler o perfil das mãos passa.
3. **O palco mora onde for servido.** Os caminhos da raiz (`/state`, `/orb`, `/media/…`) ganham
   o prefixo num lugar só: o `fetch` que já acrescentava o token, e o `window.zeCaminho` para
   as imagens e vídeos dos cards. Do PC, sem prefixo, nada muda.
4. **`camera=0`:** o palco sobe sem pedir a câmera e sem carregar o rastreador de mãos. O resto
   (anel, avatar, cards, cenas, Foco) é o mesmo.
5. **A aba Imersão escolhe:** do PC, o palco direto, com câmera e mãos. De outro aparelho com
   tela grande (900 px ou mais), o palco pelo painel, sem câmera. No celular, segue o holograma
   leve.

## A prova (17/11/2026)

Com o servidor real do palco atrás do painel e o Chromium sem tela abrindo
`/imersao/stage.html?camera=0`: o palco subiu sem erros de JavaScript; o macaco 3D carregou pelo
repasse (forçado, porque o Chromium sem tela usa WebGL por software, e aí o palco mantém só o
anel); com o estado "speaking" e a onda, o anel mostrou "FALANDO"; e um card apresentado pelo
`/cmd` abriu no centro, com o Zé esmaecido atrás. A batida que entrega os comandos (`POST /state`)
correu a 10 por segundo pelo painel.

A prova achou um defeito antigo, que valia também no PC: o "present" com um título que ainda não
estava no palco destacava o último item tocado (quase sempre o anel do Zé) em vez de criar o
card. O diff de uma skill para aprovar nunca aparecia. O "present" passou a procurar só pelo
título.

## Consequências

- Na VPS, a Imersão mostra o Zé animado e os cards, no navegador de quem abre o painel.
- Pelo painel, o palco faz cerca de 18 pedidos por segundo (a batida dos comandos e o estado do
  anel). Numa rede lenta, o anel e a onda da voz respondem com o atraso dela.
- No Live, a onda da boca não acompanha a voz: ela vem da saída de voz do Zé, e no Live a voz sai
  pela sessão do LiveKit. Vale igual no PC.
- Os gestos pela câmera do navegador ficaram de fora, por decisão de quem usa.
