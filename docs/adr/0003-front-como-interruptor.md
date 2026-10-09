# 0003 — Janela do Barehands como liga/desliga

- Data: 06/10/2026
- Status: **Aceito** (pedido do usuário)

## Contexto
O JARVIS atual escuta e fala o tempo todo, inclusive lendo sessões que o usuário conduz pelo
teclado, o que atrapalha quando ele está ouvindo outra coisa.

## Decisão
Janela do Barehands aberta = JARVIS ativo. Fechada = inativo: microfone fechado, sem fala, sem
cards. Automações continuam, mas o resultado espera; ao reativar sai **um** resumo falado.

## Consequências
- O microfone deixa de ficar aberto o dia todo: ganho de privacidade e de CPU.
- Sinal escolhido na Prova 3 (06/10/2026): **eventos do Hyprland** (`.socket2.sock`:
  `openwindow`/`closewindow` da classe `chrome-127.0.0.1__stage.html-Default`), com conferência
  por `hyprctl clients -j` ao iniciar, ao reconectar o socket e a cada 5 s. Na dúvida (socket caído
  e consulta falhando) o JARVIS fica **inativo** (falhar fechado). Números no
  [roteiro](../roteiro.md).
- O anel precisa mostrar claramente o estado inativo para não parecer travado.
