# 0017 — A sessão de código é o terminal real do agente

- Data: 12/10/2026
- Status: **Aceito** (pedido do usuário: modelos com as versões e os comandos como `/effort` dentro
  da sessão, "terminal estilo Orca")

## Contexto
A tela da sessão era uma conversa desenhada pelo painel em cima do modo sem tela dos agentes
(`claude -p` pelo Agent SDK, `codex exec`). Cada recurso do agente precisava ser refeito no painel:
modelo, versão, esforço, `/compact`, aprovações, e cada versão nova dos agentes traz outros. O
painel sempre ficaria atrás.

## Decisão
1. Cada sessão abre o `claude` ou o `codex` de verdade num pseudo-terminal (`jarvis/oficina/terminal.py`,
   `pty.fork`), na pasta e na conta da sessão. O painel desenha o terminal com o xterm.js (MIT,
   servido pelo próprio painel, sem CDN) e lê a saída por long-poll a partir de uma posição; a saída
   fica num buffer de 512 KB, então reabrir a tela mostra o que já passou.
2. Modelo, esforço e os demais comandos são os do próprio agente (`/model`, `/effort`...). O painel
   mantém o que é do Zé: agente e conta (a troca fecha o terminal e reabre com o resume nativo ou
   com a passagem, ADR 0016), o aviso de créditos esgotados, o explorador de arquivos e os anexos
   (o arquivo sobe para a pasta da sessão e o caminho vai para o terminal).
3. A conversa do Zé continua existindo, alimentada pelo próprio agente: os hooks do Claude
   (`UserPromptSubmit`, `Stop`, `Notification`) e o `notify` do Codex (`agent-turn-complete`, com
   os pedidos e a resposta) escrevem num `eventos.jsonl` da sessão. Dela saem a passagem entre
   agentes, o aviso de fim de turno e o que o cérebro lê com `sessao_ler`.
4. O cérebro e a voz mandam pedidos para a sessão colando no terminal (colagem entre colchetes e
   Enter); sem terminal aberto, o Zé abre um com o pedido.
5. A pasta do projeto é marcada como confiável no perfil da conta (Claude: `hasTrustDialogAccepted`;
   Codex: `trust_level` no `config.toml` da conta), senão o agente para na pergunta de confiança.
6. A política de segurança do painel passa a aceitar estilo inline (`style-src 'unsafe-inline'`):
   o xterm.js gera o CSS de fonte e cores. Scripts continuam só do próprio painel.

## Consequências
- O painel fica menor (sai o chat, os seletores de modelo e esforço) e acompanha os agentes sem
  trabalho: o que a versão nova do agente trouxer aparece na sessão.
- O modo sem tela continua no código para os testes (`rodar=`), mas não é mais o padrão.
- Testado de ponta a ponta no navegador (12/10/2026, Codex 0.160.1, Claude Code 2.1.291): pedido
  digitado no terminal do Codex e respondido; troca para o Claude na mesma sessão, que assumiu com
  a passagem e o estado do git.
