# 0021 — Rostos e a escolha "Escuta": a voz sem depender do Hyprland

- Data: 12/10/2026
- Status: **Aceito** (generaliza o [ADR 0003](0003-front-como-interruptor.md); primeiro passo do
  [plano da voz remota](../plano-voz-remota.md))

## Contexto
O Zé só ficava ativo (microfone aberto para o "Ei Zé") com a janela dele aberta no Hyprland. Em
qualquer outro Linux (Ubuntu com GNOME, KDE) ele ficava inativo para sempre: painel, sessões e
cérebro funcionavam, a voz não. A voz remota (celular, VPS) também precisa ligar o Zé sem janela.

## Decisão
1. **Rostos** (`jarvis/presenca/rostos.py`): o Zé fica ativo enquanto existir pelo menos um rosto
   e volta a inativo quando o último sai. Rostos de agora: `janela` (a janela do Zé no Hyprland) e
   `sempre` (a escolha "Escuta: Sempre"). O próximo: o dispositivo conectado pela voz remota.
2. **Escolha "Escuta"** na página Voz, guardada em `<config>/escuta.json`:
   - **Sempre**: o chamado funciona enquanto o Zé estiver rodando;
   - **Com a janela aberta**: só com a janela aberta. Requer Hyprland; sem ele, vale "Sempre".
   O padrão segue a máquina: com Hyprland, "Com a janela aberta" (o comportamento anterior); sem
   ele, "Sempre". O modo de fala Silencioso continua desligando o chamado (ADR 0018).
3. **Hyprland detectado, não suposto:** o monitor de janelas só sobe com o `hyprctl` e uma
   instância em execução.
4. **Microfone do sistema como reserva:** o configurado (`omarchy_mic_fx`, do Omarchy) quando
   existe; senão o microfone padrão do sistema.

## Consequências
- A voz funciona em qualquer Linux com PipeWire ou PulseAudio (`parec`, `pactl`, `paplay`).
- "Sempre" mantém o microfone aberto enquanto o Zé roda; o "Ei Zé" continua sendo detectado só na
  máquina, e o Deepgram só abre depois do chamado, como antes.
- A voz remota entra como mais um rosto, sem mudar a máquina de estados.
