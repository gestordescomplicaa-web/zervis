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
   Os nomes levam a versão (Opus 5.5, Sonnet 5.5, Haiku 4.5, Fable 5.1) e o identificador exato
   do modelo, também nas sessões. Antes de trocar, o Zé testa o modelo: o Fable 5.1 pede
   créditos de uso fora da assinatura, e a escolha é recusada com essa razão, sem quebrar nada.
2. **"Voz rápida" parecia uma quarta coisa.** Ela é um atalho do cérebro, não voz. **Corrigido:**
   chama-se **Respostas rápidas** e fica logo abaixo do Cérebro.
3. **O modelo das Respostas rápidas era um campo de texto livre.** **Corrigido:** com Claude,
   Codex e Anthropic, a mesma lista com a versão do cérebro; OpenAI, OpenRouter e Ponte (modelos
   demais para listar) continuam com o campo livre.
4. **Com o cérebro no Codex, a lista mostrava o primeiro modelo como escolhido**, quando valia o
   padrão da conta. **Corrigido:** opção "Padrão da conta".
5. **O OmniRoute não aparecia no painel** (o cérebro já sabia usá-lo, só pela configuração).
   **Feito:** Cérebro → **OmniRoute**, com Endereço e Chave de API do OmniRoute de quem usa (na
   própria máquina por http, ou num servidor por https), Testar conexão e a lista de modelos vinda
   do próprio OmniRoute; e o motor **OmniRoute** nas Respostas rápidas, com a mesma conexão.
   Salvar a conexão vale só no próprio PC.
6. **Trocar a conta não atualizava a lista das Respostas rápidas** (a conta Plus do Codex libera
   outros modelos). **Corrigido:** ao trocar ou remover uma conta, as listas do Cérebro e das
   Respostas rápidas são recarregadas.

## Passos

### Passo 1. Escolher o modelo do cérebro

- **Como:** Modelos → Cérebro → Modelo → Opus 5.5 (e, para ver a recusa, Fable 5.1). Depois, "Ei Zé, me lembra daqui a um minuto de
  beber água".
- **Esperado:** "Modelo do cérebro: Opus 5.5."; o pedido funciona, e o registro mostra o Opus 5.5.
  O Fable 5.1, sem créditos de uso, é recusado e o modelo em uso continua.
- **Resultado:** ✅ 13/10/2026. Trocou para Opus 5.5 e de volta para Sonnet 5.5; depois, para o
  Codex.

### Passo 2. Cérebro Codex

- **Como:** Modelos → Cérebro → Codex; escolher um modelo; fazer um pedido com ação.
- **Esperado:** o Codex responde e age; voltar para Claude funciona.
- **Resultado:** ✅ 13/10/2026. O Codex atendeu os pedidos e a troca de volta para o Claude
  funcionou; as Respostas rápidas também passaram a usar o Codex (GPT-6-Luna).

### Passo 2b. Cérebro pelo OmniRoute

- **Como:** Modelos → Cérebro → OmniRoute; colar o endereço e a chave do OmniRoute; Salvar;
  Testar conexão; escolher um modelo da lista; fazer um pedido com ação.
- **Esperado:** "Conectado: N modelos."; o cérebro troca para o OmniRoute e o pedido funciona.
- **Resultado:** ⬜ pendente (a pessoa vai recuperar a chave do OmniRoute).

### Passo 3. Respostas rápidas

- **Como:** desligar e ligar; Testar; "Ei Zé, tudo bem?".
- **Esperado:** ligada, a conversa simples vai pelo atalho; desligada, tudo vai ao cérebro.
- **Resultado:** ✅ 13/10/2026. Desligada, os dois pedidos foram ao cérebro (Claude); ligada, o
  atalho voltou (Claude pelo plano; antes, pelo Codex).

### Passo 4. Contas

- **Como:** ver as contas de cada agente; trocar a conta em uso (se houver mais de uma).
- **Esperado:** o cérebro e as sessões passam a usar a conta escolhida.
- **Resultado:** ✅ 13/10/2026. Trocou para a conta Plus do Codex; o Cérebro mostrou os modelos
  dela e funcionou. A lista das Respostas rápidas não acompanhava (achado 6, corrigido).

### Passo 5. Chave de API da Anthropic (opcional)

- **Como:** só se a pessoa usar chave em vez do login; Testar conexão.
- **Esperado:** "Chave válida." e o cérebro funcionando por ela.
- **Resultado:** não se aplica (a pessoa usa a assinatura).

**Área fechada em 13/10/2026**, com o passo 2b (OmniRoute) pendente até a pessoa recuperar a
chave dele.
