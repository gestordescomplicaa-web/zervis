# 0023 — Voz ao vivo: "Conectar voz" ouve sem parar até desconectar

- Data: 12/10/2026
- Status: **Aceito** (pedido do usuário: "Conectar voz" é o modo ao vivo, que ouve, executa e
  avisa de forma ininterrupta; o botão de falar é outro mecanismo, que ouve só quando apertado).
  Ajusta o [ADR 0022](0022-ativacao-e-segurar-para-falar.md) no ponto 3.

## Decisão
1. **Conectado é ao vivo.** Com a voz conectada (navegador do PC ou do celular), o Zé fica
   ouvindo sem o chamado: cada frase é um pedido; depois da resposta, volta a ouvir. Na máquina
   de estados: evento `AoVivo(ligado)`; o silêncio não encerra a escuta; "ok", hesitação ("hum")
   e ruído são ignorados, sem "Não consegui entender". Desconectar volta ao normal.
2. **Avisos ao vivo** são falados nas pausas: com a pessoa no meio de uma frase (ou o pedido dela
   sendo transcrito), o aviso espera na fila e sai na pausa seguinte.
3. **O botão de falar é um pedido só:** fora do ao vivo, depois da resposta o Zé espera o botão de
   novo (não abre a conversa contínua). Em Mãos livres, o aviso só abre a escuta com a ativação
   "Ei Zé".
4. **A ativação ("Ei Zé" ou Só o botão) vale para o microfone do computador.** A voz conectada é
   sempre ao vivo; para poupar bateria no celular, desconecta-se (e, adiante, a espera depois de
   um tempo parado).

## Consequências
- Tudo o que se fala perto do microfone conectado vai ao Zé; quem divide o ambiente desconecta ou
  usa o botão no computador.
- O "Ei Zé" e o botão continuam interrompendo a fala do Zé no ao vivo.
