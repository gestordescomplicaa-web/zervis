# Auditoria 2: Cérebro e contas

Área 2 do checklist (`docs/checklist.md`). Um passo por vez, como na auditoria de voz.

**Conceito.** O Zé tem três escolhas independentes de "quem faz o trabalho":

| | O que é | Onde se escolhe |
|---|---|---|
| **Voz** | ouvir (Deepgram) e falar (Piper) | página Voz (auditoria 1) |
| **Cérebro** | o Zé em si: entende, decide e usa as ferramentas. Tem um atalho, as **Respostas rápidas**, para conversa simples com um modelo leve | Modelos → Cérebro |
| **Sessões de código** | agentes trabalhando nos projetos da pessoa | em cada sessão (agente, modelo, conta) |

As **contas** (Modelos → Contas) são os logins dos agentes nesta máquina; o cérebro e as sessões
usam a conta em uso de cada agente.

## Achados

1. **O modelo do cérebro não se escolhia no painel** (só Claude ou Codex; o modelo ficava fixo na
   configuração). **Corrigido em 13/10/2026:** Modelos → Cérebro → Modelo, com a mesma lista das
   sessões (Claude: Opus, Sonnet, Haiku; Codex: os modelos do plano da conta). Vale na hora e
   depois de reiniciar (`<estado>/cerebro-modelos.json`).
2. **"Voz rápida" parecia uma quarta coisa.** Ela é um atalho do cérebro, não voz. **Corrigido:**
   chama-se **Respostas rápidas** e fica logo abaixo do Cérebro.

## Passos

### Passo 1. Escolher o modelo do cérebro

- **Como:** Modelos → Cérebro → Modelo → Opus. Depois, "Ei Zé, me lembra daqui a um minuto de
  beber água".
- **Esperado:** aviso "Modelo do cérebro: Opus."; o pedido funciona, e o registro mostra o Opus.
- **Resultado:** ⬜

### Passo 2. Cérebro Codex

- **Como:** Modelos → Cérebro → Codex; escolher um modelo; fazer um pedido com ação.
- **Esperado:** o Codex responde e age; voltar para Claude funciona.
- **Resultado:** ⬜

### Passo 3. Respostas rápidas

- **Como:** desligar e ligar; Testar; "Ei Zé, tudo bem?".
- **Esperado:** ligada, a conversa simples vai pelo atalho; desligada, tudo vai ao cérebro.
- **Resultado:** ⬜

### Passo 4. Contas

- **Como:** ver as contas de cada agente; trocar a conta em uso (se houver mais de uma).
- **Esperado:** o cérebro e as sessões passam a usar a conta escolhida.
- **Resultado:** ⬜

### Passo 5. Chave de API da Anthropic (opcional)

- **Como:** só se a pessoa usar chave em vez do login; Testar conexão.
- **Esperado:** "Chave válida." e o cérebro funcionando por ela.
- **Resultado:** ⬜
