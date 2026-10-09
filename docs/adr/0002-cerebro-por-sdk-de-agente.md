# 0002 — Cérebro pelos SDKs oficiais de agente, ferramentas por MCP

- Data: 06/10/2026
- Status: **Aceito** — Provas 1 (Claude) e 2 (Codex) confirmadas em 06/10/2026; OmniRoute como terceiro provedor no [0008](0008-omniroute-como-provedor-do-cerebro.md)

## Contexto
Hoje o "cérebro" é um painel do Orca: o JARVIS digita o pedido no terminal e lê a resposta pelo
`worktree ps`. Isso o torna "mais uma sessão", espera a resposta inteira antes de falar e obriga a
aprovar permissões apertando teclas na tela (o que o modo automático do Claude bloqueia entre
agentes). O usuário quer Claude e Codex, por assinatura ou API.

## Decisão
- Interface interna `Brain` única.
- **ClaudeBrain** pelo `claude-agent-sdk`: sessão contínua, texto parcial para falar por frase,
  `can_use_tool` para aprovação falada nativa, login de assinatura do Claude Code ou chave de API.
- **CodexBrain** pela via oficial que a Prova 2 apontar (SDK do Codex ou `codex app-server` /
  `codex exec --json`).
- **Ferramentas do JARVIS num servidor MCP** (`jarvis`): memória, histórico, skills, automações,
  avisos, oficina. Os dois cérebros consomem o mesmo servidor — é isso que mantém o JARVIS agnóstico.
- O JARVIS não implementa OAuth próprio.
- **Autenticação inicial só por login de assinatura** (como o usuário já usa o Claude e o Codex).
  Chave de API fica como opção de configuração, sem prioridade.

## Risco a confirmar na Prova 1: uso do Agent SDK pela assinatura
A política da Anthropic mudou várias vezes em 2026. O artigo oficial "Use the Claude Agent SDK
with your Claude plan" descreve um **crédito mensal separado** para uso do Agent SDK nos planos
Pro/Max (a partir de 15/06/2026), e há relatos de que essa mudança foi pausada. Uso pessoal, com
prompts e saídas do próprio dono da assinatura, é o caso permitido; oferecer o login a terceiros não é.
A Prova 1 precisa registrar **de onde sai o consumo** (limite normal da assinatura ou crédito do
Agent SDK) e o tamanho dele. Atenção: segundo a mesma página, o crédito também cobre o comando
`claude -p`, então ele **não** é alternativa. Se o crédito for pequeno demais, a alternativa é um
`ClaudeBrain` que conversa com uma sessão **interativa** do Claude Code num painel do Orca (o modelo do
JARVIS antigo, já testado), mantendo a mesma interface `Brain`; ou usar o Codex como cérebro principal.

## Por que MCP, se tudo é local
"MCP" aqui não é um serviço na rede nem exige chave de API. É só o **formato** em que os dois
SDKs aceitam ferramentas personalizadas:
- No Claude Agent SDK, as ferramentas do JARVIS rodam **dentro do mesmo processo**
  (servidor MCP em memória do próprio SDK): sem porta, sem rede, sem processo extra.
- No Codex, ferramentas extras entram como servidor MCP por **stdio** (um subprocesso local
  falando por entrada e saída padrão): também sem porta de rede.
- A alternativa seria escrever cada ferramenta duas vezes, uma por cérebro. Com MCP, escreve-se
  uma vez e os dois usam. Nada fica exposto em `localhost`.

### Resultado da Prova 1 (06/10/2026)
O Agent SDK funcionou com o login de assinatura (plano Pro) e o consumo apareceu na **janela
normal de 5 horas** da assinatura, sem crédito separado visível. Primeira frase completa em
1,5–2,1 s após o pedido (primeiro texto em 0,8–1,5 s). Números e detalhes no
[roteiro](../roteiro.md). A política pode mudar de novo: o `jarvisd` deve registrar os eventos
de limite (`RateLimitEvent`) no `status.json` para notar a mudança.

### Resultado da Prova 2 (06/10/2026): Codex pelo `codex app-server`
Via escolhida: **`codex app-server`** (JSON-RPC por stdio, uma mensagem JSON por linha; Codex CLI
0.159.2), não o `exec --json`. Ele cobre tudo o que a interface `Brain` pede:
- sessão contínua (`thread/start`, `ephemeral`), streaming de texto (`item/agentMessage/delta`),
  interrupção (`turn/interrupt`), persona por `developerInstructions`;
- **MCP por stdio** configurado por `-c mcp_servers.jarvis.*`, com aprovação por ferramenta
  (`tools.<nome>.approval_mode = "approve" | "prompt"`);
- **aprovação no cliente**: o servidor pede (`mcpServer/elicitation/request` para MCP,
  `item/commandExecution/requestApproval` para comandos) e o JARVIS responde. Na prova, a
  ferramenta com `prompt` foi pedida, negada e **não executou**;
- cota da assinatura legível por `account/rateLimits/read`.

Números (`provas/prova2_codex.py`, plano Plus, modelo padrão `gpt-6-luna`): conexão 0,64 s;
primeira frase 3,99 s no 1º turno e 1,70 s no 2º. Cada turno manda ~19,5 mil tokens de entrada
(o prompt próprio do Codex; ~57–98% em cache), contra ~470 do Claude.

Cuidados para o `CodexBrain` (Fase 8):
- Usar um `CODEX_HOME` próprio do JARVIS: o padrão carrega os MCPs globais do usuário (ai-memory,
  blender, apps), e o `CODEX_HOME` herdado do Orca pode estar sem login.
- Ler stdout com limite de linha grande (16 MB): linhas do app-server passam de 64 KB e, com o
  limite padrão do asyncio, o leitor morre calado.
- Responder a pedidos desconhecidos do servidor com erro (falhar fechado).
- **Cota:** a janela semanal do Plus estava em 88% em 06/10/2026; como cérebro principal o Codex
  disputaria cota com as sessões de código do Orca. Fica como provedor alternativo.

## Consequências
- O painel "JARVIS ORCA" no Orca deixa de ser necessário (Fase 9, uso diário).
- Uso por assinatura conta no plano do usuário como qualquer sessão.
- Se a Prova 2 mostrar que o Codex não oferece streaming ou aprovação equivalentes, o CodexBrain
  entra com limitações documentadas, não o contrário (a interface não se degrada pelo pior caso).
