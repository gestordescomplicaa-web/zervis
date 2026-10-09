# 0007 — Cérebro base rápido; codificação com os agentes do Orca

- Data: 06/10/2026
- Status: **Aceito** (decisão do usuário)
- Refina: [0002](0002-cerebro-por-sdk-de-agente.md) e [0006](0006-orca-continua-como-oficina.md)

## Decisão
1. O JARVIS tem **um cérebro base central**: rápido, com inteligência suficiente para conversa,
   memória, skills, automações, controle da máquina e para **decidir e delegar**. Ele não coda.
2. **Codificar e avaliar projetos em aberto é trabalho dos agentes do Orca**, com os provedores e
   modelos que o usuário configurar lá. O cérebro base delega pela ferramenta `oficina`
   (orquestração do Orca) e relata o resultado.
3. Critério de escolha do cérebro base: **latência primeiro** (primeira frase falada em ~1 s),
   depois custo e qualidade. Candidatos para as Provas 1 e 2: um modelo rápido do Claude pelo
   Agent SDK (assinatura) e um modelo rápido do Codex pelo `codex app-server` (login do ChatGPT).

## Consequências
- O cérebro base não precisa das ferramentas de código do Claude Code (editar arquivos, terminal
  amplo): só as ferramentas do JARVIS via MCP. Prompt menor, resposta mais rápida, menos riscos.
- O consumo do cérebro base tende a ser pequeno, o que reduz o risco do crédito separado do Agent
  SDK (ADR 0002). Ainda assim a Prova 1 mede.
- A interface `Brain` continua trocável: o usuário escolhe o provedor do cérebro base na config.
