# 0079 — No PC, o Zé é um programa

- Data: 11/11/2026
- Status: **Aceita** (o atalho com um systemd de mentira em `tests/test_instalador_pc.py`).

## Contexto

O instalador de PC reaproveitava o do servidor e ligava a partida automática: o Zé subia com o
computador e ficava escutando o "Ei Zé" sem janela nenhuma aberta. Em 11/11/2026 ele atendeu a
fala de um vídeo do Instagram sem que ninguém o tivesse aberto, e quem usa nem sabia que ele
estava ligado. No PC, o esperado é o de um programa: funciona quando está aberto.

## Decisão

1. **No PC, sem partida automática.** O instalador liga o Zé para a configuração inicial e não o
   habilita no login. No servidor (VPS), nada muda: ele fica sempre de pé.
2. **Abrir liga, fechar desliga.** O atalho (`deploy/abrir-painel.sh`) liga o serviço, espera o
   painel responder e abre a janela. Quando a última janela do Zé fecha (a do programa ou a da
   Imersão que ele abre por voz), o atalho desliga o serviço: fechado, ele não escuta nem faz nada.
3. **Quem quiser o Zé sempre ligado** habilita a partida automática
   (`systemctl --user enable zervis`); aí fechar a janela não desliga nada, como antes. O
   `zervis doctor` mostra os dois casos sem marcar nenhum como problema.
4. As sessões de código seguem na supervisora delas (`zervis-oficina`, ADR 0068): fechar o Zé
   não interrompe um agente no meio de uma tarefa.

## Consequências

- Com o programa fechado não há lembretes, automações, WhatsApp, ligações, app de voz no
  celular nem acesso remoto.
- Sem Chromium (aberto pelo navegador padrão), o atalho não sabe quando a aba fecha, e o Zé fica
  ligado até `systemctl --user stop zervis`.
