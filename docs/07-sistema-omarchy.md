# 07 — O sistema (Omarchy 4) como parte do núcleo

Data: 06/10/2026. Máquina: Omarchy 4.0.4 (Arch Linux, Hyprland 0.56, shell Quickshell).

O Zé é um sistema **da máquina local**: ele lê o estado do computador e opera o computador.
Os outros sistemas se adaptam a ele, e não o contrário. O Omarchy torna isso barato, porque já
expõe quase tudo como comandos documentados.

## O que o Omarchy oferece (verificado)

### 1. Catálogo de ações legível por máquina
- `/usr/bin/omarchy-*`: **445 comandos**, dos quais **443** trazem no cabeçalho
  `# omarchy:summary=…`, `# omarchy:args=…` e `# omarchy:examples=…` (alguns com `omarchy:hidden=true`).
- O Zé gera o próprio catálogo lendo esses cabeçalhos, sem lista escrita à mão, e ele se
  atualiza sozinho a cada atualização do Omarchy.
- Grupos relevantes no dia a dia:

| Grupo | Exemplos | Uso pelo Zé |
|---|---|---|
| Leitura de estado | `system-stats`, `battery-status`, `network-status`, `monitor-state`, `update-available`, `weather-status`, `theme-current`, `version` | Responder "como está a máquina?" |
| Áudio e tela | `audio-output-volume`, `audio-output-switch`, `audio-input-mute`, `brightness-display`, `toggle-nightlight` | Comandos de voz rápidos |
| Janelas e apps | `launch-or-focus`, `launch-browser`, `launch-editor`, `hyprland-focus-app`, `hyprland-window-close-all` | "Abre o navegador", "foca o Orca" |
| Captura | `capture-screenshot`, `capture-region`, `capture-text` | "Lê o que está na tela" |
| Notificações | `notification-send`, `notification-dismiss`, `toggle-notification-silencing`, `reminder` | Saída visual quando a voz não cabe |
| Aparência | `theme-set`, `theme-list`, `theme-bg-next` | O tema do Barehands pode seguir o do sistema |
| Agentes | `agent`, `agent-prompt`, `agent-usage-claude`, `agent-usage-codex` | Ler o uso dos planos Claude/Codex; abrir o agente padrão |
| Voz do sistema | `voxtype-status`, `voxtype-model` | Convivência com o ditado do F9 |
| Sistema (risco) | `system-reboot`, `system-shutdown`, `update`, `pkg-install`, `pkg-remove`, `system-factory-reset` | Só com confirmação forte, ou bloqueado |

### 2. Eventos do sistema (hooks)
- `omarchy-hook <nome>` roda `~/.config/omarchy/hooks/<nome>` e os scripts em `<nome>.d/`.
- Pastas já existentes na máquina: `battery-low.d`, `font-set.d`, `post-boot.d`, `post-update.d`,
  `pre-refresh-pacman.d`, `theme-set.d`.
- O Zé pode instalar **um script pequeno em cada pasta `.d`** que só avisa o serviço do Zé
  (escreve uma linha num socket/FIFO local). Assim "bateria fraca", "atualização terminou" e
  "tema mudou" viram eventos do Zé sem *polling*.
- Instalação desses hooks altera `~/.config/omarchy`: feita uma vez, com aprovação, seguindo a
  skill `omarchy` (nunca editar `/usr/share/omarchy`).

### 3. Estado persistente
- `~/.local/state/omarchy/` (gerido por `omarchy-state set|clear`): toggles e ajustes.
- A agenda do Omarchy fica em `~/.local/state/omarchy/calendar-events.json` (fonte que o antigo
  monitor do Hermes lia e que ficou sem dono).

### 4. Hyprland
- `hyprctl -j` (clientes, workspaces, janela ativa, monitores) para **ler** a mesa de trabalho.
- Socket de eventos do Hyprland (`.socket2.sock` em `$XDG_RUNTIME_DIR/hypr/<assinatura>/`) para
  saber, sem *polling*, quando uma janela abre ou fecha, inclusive a do Barehands (candidato ao
  sinal do interruptor, Prova 3).

## Política de risco das ações do sistema

| Nível | Exemplos | Regra |
|---|---|---|
| 0 — leitura | stats, bateria, rede, janela ativa, agenda | Livre |
| 1 — ação reversível | volume, brilho, abrir/focar app, notificação, tema, screenshot | Executa e diz o que fez |
| 2 — ação com efeito durável | instalar pacote, mudar padrão, fechar todas as janelas | Confirmação falada ("sim/não") |
| 3 — sistema | reiniciar, desligar, atualizar o sistema | Confirmação falada **com a palavra exata** ("confirmo reiniciar") |
| 4 — proibido | `system-factory-reset`, `remove-*` de segurança, qualquer `sudo` | Nunca, nem por voz |

A tabela vira configuração com valores padrão seguros; comando novo do Omarchy que não está
classificado cai no nível 2.

## Lições do ambiente que entram como regra
- Serviços com `PartOf=graphical-session.target` caem quando o Hyprland reinicia e não voltam
  sozinhos (crash de 06/10/2026). O serviço do Zé não usa esse vínculo.
- Em 06/10/2026 o Hyprland caiu ao criar um teclado virtual (suspeito: fcitx5). O Zé **não**
  deve simular teclado (`wtype`/`ydotool`) como forma de agir; prefere comandos e IPC.
- Processos órfãos de ferramentas de agente já consumiram ~130% de CPU sem ninguém do outro
  lado. O Zé pode vigiar isso (nível 0) e sugerir encerrar (nível 2).
