# Plano — voz remota: falar com o Zé de qualquer lugar (12/10/2026)

**Estado (12/10/2026):** etapa 0 feita (ADR 0021). Etapa 1 feita no código e provada por um
participante de teste (entrar na sala liga o Zé e fecha o microfone local; pedido respondido com a
voz chegando pela faixa; sair desliga). Falta a prova de ouvido pelo navegador: o "Ei Zé" com o
microfone do navegador e a latência medida.

Pedido do usuário: um canal de voz próprio com o Zé, sem passar pelo WhatsApp, para operá-lo de
longe (celular, outro computador) e, depois, com o Zé ligado 24 horas numa VPS. É o diferencial
do Zé diante do Hermes, do OpenClaw e do Paperclip: eles conversam por texto em aplicativos de
mensagem; o Zé conversa por **voz em tempo real**, avisa por voz quando uma sessão termina, falha
ou pede aprovação, e opera sessões de código com várias contas Claude e Codex.

Evolui o [ADR 0005](adr/0005-celular-por-livekit-e-tailscale.md) (celular por LiveKit e
Tailscale), que já previa o desenho; este plano o detalha, traz para antes no roteiro e
acrescenta a VPS. Vira ADR próprio quando a etapa 1 provar o caminho.

## Decisões

1. **Desenvolver no localhost, não na VPS.** As sessões de código, os projetos, os logins do
   Claude e do Codex e o microfone estão no PC; testar voz exige ouvir. O LiveKit roda no próprio
   PC durante o desenvolvimento, e o mesmo código vai para a VPS na etapa 4, sem mudança.
2. **Só o transporte muda.** O Zé entra numa sala LiveKit como participante (SDK Python `livekit`,
   só sala e faixas, sem o framework de agentes). Ativação, escuta, Deepgram, cérebro, modos de
   fala, interrupção e Piper continuam os mesmos. A porta já existe: `jarvis/transporte/`.
3. **"Ei Zé" é detectado no Zé, onde quer que ele rode.** O áudio vai do dispositivo para o
   servidor do próprio usuário (PC ou VPS), não para terceiros; o Deepgram só abre depois do
   chamado, como hoje. Privacidade igual à do modo mesa.
4. **Nada exposto na internet aberta.** Rede privada (Tailscale ou WireGuard) entre os
   dispositivos do usuário; o painel e o LiveKit só respondem dentro dela.
5. **LiveKit gerenciado pelo Zé**, como o ai-memory e o Piper: binário oficial baixado e conferido
   por SHA-256, configuração gerada na primeira subida (chave e segredo aleatórios em arquivo
   0600), processo filho supervisionado. Sem Docker obrigatório: vale para qualquer Linux.
6. **Reaproveitar o Ligatia** (do mesmo autor): fluxo de token, ponte de áudio, softphone no
   navegador e as lições de jitter. Ao entrar no Zé, esse código passa a ser AGPL e público.

## Topologia

```text
Etapas 1 a 3: o Zé no PC
  celular / notebook ──(Tailscale, HTTPS)──▶ painel do Zé (PC) ──▶ token curto
  navegador (microfone, WebRTC) ──────────▶ livekit-server (PC) ◀──▶ Zé (participante)

Etapa 4: o Zé no servidor
  PC (estação de voz, painel)  ─┐
  celular (PWA)                ─┼──(Tailscale)──▶ VPS: Zé + livekit-server + sessões da VPS
  outro computador             ─┘
```

Com o Zé no PC, ele responde de qualquer lugar enquanto o PC estiver ligado. Com o Zé na VPS, ele
fica ligado 24 horas e opera as sessões dos projetos que estão lá; comandar de lá as sessões do PC
é a etapa 6.

## Peças

| Peça | Onde | O que faz |
|---|---|---|
| `jarvis/transporte/livekit.py` | Zé | Entra na sala; recebe a faixa da pessoa em quadros de 80 ms a 16 kHz (mesma fila da `Captura` local); publica a voz do Piper numa `rtc.AudioSource` (reamostragem para 48 kHz). |
| Rostos (presença generalizada) | Zé | O Zé fica ativo quando existe um rosto: janela do painel no Hyprland, interruptor "Escuta" ligado, ou dispositivo conectado na sala. Substitui a dependência exclusiva do Hyprland. |
| `voz/token` | portal | Emite token LiveKit só com sessão do painel válida: uma sala da instalação, validade de 10 min, identidade por dispositivo, publicar só áudio. |
| Botão "Conectar voz" | painel | Liga o microfone do navegador (`livekit-client`, Apache-2.0, vendorizado) com cancelamento de eco, anel de estado, nível do microfone, desconectar. |
| PWA | painel | Manifesto para instalar o painel no celular como aplicativo. |
| `livekit-server` | Zé (filho) | Binário oficial, config gerada, só no endereço local (7880 TCP para a sinalização, 7882 UDP para a mídia, sem TCP de mídia); na etapa 2, o endereço da rede privada. |
| Login do painel | portal | Senha mais código (TOTP) ou passkey, exigido fora do localhost. |

## Como a pessoa usa

- **Conectar** no painel (PC, celular ou outro computador): a voz abre com o Zé.
- Três formas de chamar, escolhidas na página Voz:
  - **Chamado** ("Ei Zé"): o Zé escuta o canal e só reage ao chamado, como na mesa.
  - **Apertar para falar**: botão na tela ou o botão do fone.
  - **Conversa aberta**: enquanto conectado, tudo é pedido; "ok" ou silêncio longo encerra.
- **Modos de fala** valem igual (ADR 0018): em Mãos livres, os avisos das sessões chegam no
  dispositivo conectado; sem dispositivo conectado, ficam na fila de avisos.
- Um dispositivo conectado por vez; conectar outro assume a conversa (como trocar de fone).

## Segurança

| Ameaça | Defesa |
|---|---|
| Alguém na internet acha o painel ou o LiveKit | Nada escuta fora da rede privada; nenhuma porta aberta no roteador ou na VPS além da rede privada. |
| Dispositivo da rede privada sem dono legítimo | Login no painel (TOTP ou passkey) antes de qualquer token. |
| Token vazado | Validade de 10 min, uma sala, só publicar áudio; segredo do LiveKit em arquivo 0600, nunca na tela nem no log. |
| Gravação indevida | O Zé não grava áudio; o Deepgram só depois do chamado; registros sem áudio nem transcrição. |
| Ação perigosa por voz de terceiros | Aprovações continuam com confirmação falada e, para as destrutivas, confirmação na tela. |
| VPS comprometida | Endurecimento da VPS (do Ligatia: `HARDENING-VPS.md`), usuário sem root, atualizações automáticas. |

## Etapas (cada uma com critério de pronto, medida e commit próprio)

0. **Pré-requisitos.** Salvar o trabalho atual em commits por assunto. Interruptor "Escuta" e
   rostos: a voz funciona em qualquer Linux, sem depender da janela no Hyprland.
   *Pronto quando:* num Ubuntu com GNOME o "Ei Zé" funciona com o interruptor ligado.
1. **Voz pelo navegador no próprio PC.** `livekit-server` gerenciado pelo Zé,
   `TransporteLiveKit`, `voz/token` e o botão "Conectar voz".
   *Pronto quando:* uma conversa completa pelo navegador (chamado, pedido, resposta, interrupção)
   com latência no máximo 150 ms acima do modo mesa, medida pelas marcas de `latencia.py`.
2. **Celular pela rede privada.** Tailscale, HTTPS (`tailscale serve`), PWA.
   *Pronto quando:* a Prova 4 do ADR 0005 passar: latência no 4G, tela bloqueada, fone Bluetooth,
   o "Ei Zé" com o microfone do celular (pode pedir retreino ou "apertar para falar").
3. **Login do painel** com TOTP ou passkey, obrigatório fora do localhost.
4. **O Zé no servidor.** Modo sem tela e sem microfone local (rosto só remoto), instalação de um
   comando num Ubuntu de VPS, sessões nos projetos da VPS.
   *Pronto quando:* o Zé roda 24 horas na VPS e uma sessão de código termina com aviso falado no
   celular.
5. **Outras entradas (opcional).** Softphone SIP e WhatsApp como portas para a mesma sala,
   reaproveitando o `wacalls-bridge` do Ligatia, num número separado.
6. **Estações.** O Zé da VPS comanda sessões que rodam no PC (conexão de saída do PC para a VPS,
   autenticada), para projetos que precisam ficar na máquina.

## O que vem do Ligatia

| Do Ligatia | Para o Zé |
|---|---|
| `DASHBOARD/api.py` (`testar_agente_token`, softphone) | `voz/token`: identidade, sala e permissões do token |
| `WHATSAPP_BRIDGE/bridge.py` (`AudioStream`, `AudioSource`, reamostragem) | `jarvis/transporte/livekit.py` |
| `DASHBOARD/static/js/01-softphone.js` | Botão "Conectar voz" e telemetria do áudio no painel |
| Configuração do LiveKit em `stack.producao.yml` | Configuração gerada pelo Zé |
| `CAPACIDADE-E-ESCALA-VOZ.md`, `HARDENING-VPS.md` | Dimensionamento da VPS e endurecimento |
| `WACALLS-INTEGRACAO.md` | Etapa 5 |

## Riscos e pontos a provar

- **Navegador do celular com a tela bloqueada** pode suspender o microfone (iPhone mais
  restritivo). Saída: Android primeiro; aplicativo nativo só se a etapa 2 exigir.
- **"Ei Zé" com outro microfone** (WebRTC, fone): ganho e cancelamento de eco diferentes; pode
  exigir retreino com amostras do canal remoto.
- **Jitter numa VPS lenta** pica a voz (lição do Ligatia): medir na VPS antes de declarar a etapa 4.
- **Uma peça a mais** (`livekit-server`): supervisionada pelo Zé, com diagnóstico na página Voz.

## Fora deste plano

Chamadas de voz com outras pessoas, várias pessoas na mesma sala e aplicativo nativo para
celular.
