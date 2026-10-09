# 0005 — Celular como rosto remoto: LiveKit local + Tailscale

- Data: 06/10/2026
- Status: **Proposto, para a última fase do roadmap** (Fase 10, decisão do usuário em 06/10/2026). Celular: **Android**.
- Substitui: [0004](0004-ponte-de-audio-livekit-adiada.md)

## Contexto
O usuário quer trabalhar mãos livres longe do computador: fone no celular, Orca rodando no PC,
e o JARVIS no PC conversando com ele pelo celular. Ele pede coisas de projeto ("como está o
projeto X", "manda o Codex rodar os testes", "aprovar") e é avisado quando um agente termina,
falha ou pede permissão.

Hoje a máquina só é alcançável na rede de casa (192.168.0.6). Não há Tailscale nem LiveKit instalados.

## Decisão
1. **O celular é mais um "rosto".** O JARVIS fica ligado quando existe um rosto conectado: a
   janela do Barehands (modo mesa) **ou** o app do celular (modo remoto). Isso generaliza o
   [ADR 0003](0003-front-como-interruptor.md) sem mudar a ideia.
2. **Áudio por WebRTC com LiveKit rodando no próprio PC** (`livekit-server`, código aberto, local).
   O JARVIS entra na sala como participante pelo SDK Python de tempo real (`livekit` rtc): recebe a
   faixa do microfone do celular e publica a faixa da voz do Cadu. **Só o transporte muda**: detector
   de ativação, transcrição, cérebro, normalizador e Cadu continuam os mesmos do modo mesa.
   O framework de agentes do LiveKit não é obrigatório; usamos só a sala e as faixas.
3. **Alcance fora de casa por Tailscale** (rede privada entre os dispositivos do usuário; o
   Omarchy já tem `omarchy-install-service-tailscale`). Nada é exposto na internet aberta. O
   `tailscale serve` também resolve o HTTPS que o navegador exige para liberar o microfone.
4. **Cliente do celular:** primeiro um web app (PWA) mínimo com o SDK JavaScript do LiveKit: botão
   conectar/desconectar (o liga/desliga remoto), anel de estado, últimos avisos e pendências.
   App nativo só se a Prova 4 mostrar que o navegador perde o microfone com a tela bloqueada.

## Pontos a provar (Prova 4)
- Latência de ponta a ponta (fala → resposta audível) no Wi-Fi de casa e no 4G/5G via Tailscale.
- Comportamento com a **tela do celular bloqueada** e com o navegador em segundo plano
  (sistemas móveis costumam suspender o microfone de páginas web; o iPhone é o mais restritivo).
- Detector pessoal "Hey Orca" com o áudio do microfone do fone Bluetooth/cabo via WebRTC
  (ganho e cancelamento de eco diferentes do MIC FX do PC; pode exigir retreino).
- Botão do fone (play/pause) como alternativa à palavra de ativação ("aperta e fala").

## Consequências
- O modo remoto fica para o fim; antes vêm o núcleo, o cérebro, a oficina (Orca), memória, máquina,
  skills e automações, que valem igual na mesa e no celular. O transporte trocável da Fase 1 deixa a porta aberta.
- Segurança: a sala do LiveKit exige token assinado pelo `jarvisd`; só dispositivos do Tailscale
  do usuário chegam ao PC; aprovações continuam com confirmação falada.
- Uma peça a mais para manter (`livekit-server`), rodando como serviço de usuário e só local.
