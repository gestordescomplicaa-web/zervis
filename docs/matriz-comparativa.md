# Matriz comparativa: Hermes, OpenClaw e Zérvis

Data: 15/10/2026, com a coluna do Zérvis revisada em 19/10/2026 (conectores, sessões por
projeto, vigia do n8n e instalação na VPS). Norte do [roteiro](roteiro.md): o que cada agente faz que os outros não fazem,
para decidir o que entra no Zérvis com base em referência, e não em ideias soltas. Revisar a cada
etapa concluída.

O objetivo do Zérvis é ser o melhor assistente pessoal de trabalho: o funcionário e o gerente que
uma empresa gostaria de ter. Por isso, além das funções, a matriz olha o que esse papel exige
(seção 4).

**Método.** Hermes e OpenClaw: o que a documentação oficial afirma em 15/10/2026, sem instalar nem
executar. Zérvis: o que está no código (`jarvis/`) e foi validado. Medições na
[auditoria de 14/10](auditoria/funcionalidades-e-desempenho-2026-10-14.md).

Legenda: **●** tem · **◐** parcial ou sem validação · **—** não tem ou não documentado.

## 1. Funções lado a lado

### Voz

| Função | Hermes | OpenClaw | Zérvis |
|---|---|---|---|
| Conversa por voz em tempo real | ● terminal e mensageiros | ● Talk Mode | ● |
| Palavra de ativação | ● "Hey Hermes" | ● Voice Wake nos apps | ● "Ei Zé" universal e treino com a voz de quem usa |
| Interromper a fala do agente | — | — | ● |
| Fim de turno pela entonação | — | — | ● Smart Turn |
| Voz local, sem nuvem | ◐ dez provedores de TTS | ◐ vários provedores de TTS | ● Piper no próprio processo |
| Transcrever mensagem de voz | ● | ● | — |
| Voz pelo celular | ● pelos mensageiros | ● apps iOS e Android | ● navegador do celular, pelo HTTPS do painel |
| Pausar a música enquanto conversa | — | — | ● |

### Canais e acesso

| Função | Hermes | OpenClaw | Zérvis |
|---|---|---|---|
| Conversar pelos mensageiros | ● Telegram, Discord, Slack, WhatsApp, Signal, e-mail | ● mais de 25 (WhatsApp, Telegram, Slack, Teams, iMessage, Signal, SMS...) | — |
| Grupos com ativação por menção | — | ● | — |
| Pareamento de remetentes desconhecidos | ● | ● | — |
| Painel web | ◐ aplicativo de desktop | ● Control UI e WebChat | ● painel com configuração pela tela |
| Apps nativos | ◐ Windows e macOS | ● macOS, iOS, Android, Windows | — (painel instalável pelo navegador) |
| Acesso de fora com segurança | ● pelos mensageiros | ● SSH, Tailscale, token ou senha | ● túnel com senha e código do autenticador; Tailscale |
| API compatível com OpenAI | ● | ● | — |
| Integração com IDE (ACP) | ● VS Code, Zed, JetBrains | — | — |

### Modelos e contas

| Função | Hermes | OpenClaw | Zérvis |
|---|---|---|---|
| Vários provedores | ● mais de 300 modelos | ● Anthropic, OpenAI, Google e outros | ● Claude, Codex, OpenRouter, proxy OpenAI |
| Usar a assinatura (sem chave de API) | ◐ Nous Portal | ● OAuth de assinatura | ● Claude Code e Codex logados |
| Modelos locais (Ollama, vLLM) | ● endpoints próprios | ● | ◐ só por proxy no formato OpenAI |
| Alternativa automática se o provedor falhar | ● | ◐ | ● antes de responder ou agir, sem repetir ações |
| Várias contas do mesmo agente | ● pool de chaves | — | ● contas por agente, com cota restante |
| Via rápida para respostas curtas | — | — | ● |

### Memória e aprendizado

| Função | Hermes | OpenClaw | Zérvis |
|---|---|---|---|
| Memória entre conversas | ● MEMORY.md e USER.md | ● local | ● curta, longa e por projeto (ai-memory) |
| Busca no histórico | ● FTS5 com resumo | ◐ | ● FTS5 em SQLite e histórico pelo ai-memory |
| Modelo de quem usa | ● Honcho | — | ◐ perfil e memória |
| Provedores de memória plugáveis | ● | — | — |
| Skills no padrão agentskills.io | ● | ● | ● |
| Criar e melhorar skills sozinho | ● sem aprovação | — | ● com aprovação |
| Linha do tempo e nota do dia | — | — | ● |
| Diagnóstico do que deu errado | ◐ `hermes doctor` | ◐ `openclaw doctor` | ● diagnóstico agrupado por causa e evidências de uso |

### Trabalho e automação

| Função | Hermes | OpenClaw | Zérvis |
|---|---|---|---|
| Sessões de código com Claude e Codex | — | — | ● terminal real, cópia isolada, prévia, aplicar e descartar |
| Subagentes em paralelo | ● | ● roteamento entre agentes | ◐ sessões em paralelo; sem delegação entre agentes |
| Narrar o andamento das tarefas | — | — | ● central de avisos por voz |
| Foco: frentes de trabalho em andamento | — | — | ● |
| Tarefas agendadas | ● cron em linguagem natural | ● cron e heartbeat | ◐ agenda, lembretes e consultas |
| Entregar o resultado num canal | ● | ● | — |
| Webhooks e hooks | ● hooks | ● hooks e webhooks | — |
| Fluxos de várias etapas | — | ● Lobster | — |
| Pontos de restauração antes de mudar arquivos | ● `/rollback` | — | ◐ cópia isolada nas sessões |
| Processamento em lote | ● | — | — |
| Atender clientes (WhatsApp e ligação) | — | ◐ canal de chamada de voz | ◐ WhatsApp pareado, agente em teste, ligação em andamento |
| Leads quentes nas mensagens recebidas | — | — | ● |
| Melhorar o próprio código | — | — | ● cópia isolada, testes, aprovação e volta automática |

### Ferramentas e computador

| Função | Hermes | OpenClaw | Zérvis |
|---|---|---|---|
| Conectores MCP | ● stdio e HTTP | ● stdio, SSE e HTTP | ● stdio e HTTP: colar o JSON ou o curl do serviço, login OAuth com renovação |
| Conectores por projeto (cliente) | ◐ perfis separados | ◐ agentes e gateways isolados | ● cada sessão liga os do seu projeto; fora da conversa |
| Vigiar os sistemas dos clientes | ◐ cron sem modelo (`no_agent`) | ◐ heartbeat | ● vigia do n8n: fora do ar e de volta, sem modelo |
| Política por ferramenta | ● filtro | ● perfis e política | ● livre, com aprovação ou bloqueada |
| Navegador | ● vários backends | ● | ◐ Playwright MCP sem validação |
| Busca na web | ● | ● doze provedores | ◐ pelo agente |
| Visão e imagem colada | ● | ● | ◐ anexos nas sessões |
| Gerar imagem | ● | ● | — |
| Ações do sistema com nível de risco | ◐ uso do computador | ◐ comandos nos aparelhos | ● Omarchy, com política de risco |
| Câmera, tela e localização do celular | — | ● | — |
| Controle por gestos (modo imersivo) | — | — | ● |
| Pacotes e marketplace | ● Skills Hub e plugins | ● ClawHub e SDK de plugins | — (etapa E6, ADR 0033) |

### Segurança

| Função | Hermes | OpenClaw | Zérvis |
|---|---|---|---|
| Aprovação de comandos | ● | ● | ● falada ou pela tela |
| Execução isolada (contêiner) | ● sete backends | ● sandbox | ◐ cópia isolada para código; mesmo usuário do sistema |
| Registro de tudo o que executa | ◐ | ◐ | ● Atividade, inclusive o que foi negado |
| Zona protegida e essência | — | ◐ "política imposta por código" | ● |

## 2. Instalação

O ponto onde o Zérvis está mais atrás, e o primeiro a fechar.

| Etapa | Hermes | OpenClaw | Zérvis hoje |
|---|---|---|---|
| Um comando | `curl …/install.sh \| bash` | `curl …/install.sh \| bash` | ● na VPS (`deploy/instalar-servidor.sh`); ◐ no PC (`git clone`, `uv sync`, `make instalar`) |
| Dependências | O instalador traz uv, Python, Node, ripgrep e FFmpeg | O instalador traz o Node | Manual: uv, Go para o WaCalls, modelos baixados na primeira subida |
| Configuração inicial | Assistente no terminal (`hermes setup`) | `openclaw onboard` | ● pela tela do painel |
| Serviço do sistema | systemd de usuário, com `loginctl enable-linger` | `--install-daemon`: systemd, launchd ou Tarefa Agendada | ◐ `make instalar` (systemd de usuário) |
| Verificar a instalação | `hermes doctor` | `openclaw doctor` e `gateway status` | — |
| Atualizar | Pelo Git gerenciado | Comando próprio | ◐ só pela oficina, com testes |
| Desinstalar | Documentado | Comando próprio | — |
| Servidor sem tela (VPS) | Docker e usuário de serviço | Docker, Kubernetes, guias por provedor | ● provado do zero num Ubuntu 24.04: HTTPS, senha e autenticador |
| Plataformas | Linux, macOS, WSL2, Windows, Android | Linux, macOS, Windows, iOS, Android | Linux |

**O que falta para o Zérvis empatar no Linux e na VPS:**
1. `install.sh` que confere e instala o que falta (uv, Python fixado, o binário do WaCalls por
   SHA-256), sem precisar de Go nem de Node na máquina de quem usa.
2. Um comando `zervis` com `setup`, `doctor`, `update`, `uninstall` e `status`.
3. Perfil de servidor: sem microfone, sem janela e sem imersivo, só o painel e os canais.
4. Imagem Docker, com os dados em volume.
5. Uma máquina limpa (Linux e VPS) instalando do zero, como prova no CI.

## 3. O que só cada um tem

**Só o Hermes:** pontos de restauração (`/rollback`), integração com IDE (ACP), processamento em
lote, modelo de quem usa (Honcho), provedores de memória plugáveis, sete backends de execução,
cache de prompt de uma hora.

**Só o OpenClaw:** mais de 25 canais, grupos com menção, apps com câmera, tela e localização,
Canvas, fluxos Lobster, heartbeat, roteamento de agentes por remetente, vários gateways
isolados, recarregar a configuração sem reiniciar.

**Só o Zérvis:** voz completa na própria máquina (interrupção, fim de turno pela entonação, Piper
local), sessões de código Claude e Codex com aprovação antes de juntar, narração por voz do
andamento das tarefas, Foco, atendimento de clientes no WhatsApp, leads quentes, melhorar o
próprio código com travas, modo imersivo por gestos, configuração toda pela tela.

## 4. O papel de assistente de trabalho

O que o melhor funcionário e gerente faz, e onde cada agente está.

| O que o papel exige | Hermes | OpenClaw | Zérvis |
|---|---|---|---|
| Recebe o pedido onde a pessoa estiver (voz, mensageiro, celular) | ● | ● | ◐ voz e painel; falta mensageiro |
| Delega e acompanha trabalho de vários agentes | ● subagentes | ● vários agentes | ● sessões de código; falta além de código |
| Avisa só o que importa, sem ser cobrado | ◐ | ◐ heartbeat | ● central de avisos e modo de fala |
| Não esquece o que começou | ◐ memória | ◐ memória | ● Foco e linha do tempo |
| Retoma depois de cair, sem refazer o que já fez | — | — | ◐ falta a fila durável |
| Entrega com prova (testes, resultado verificável) | — | — | ◐ testes na oficina; falta para as outras tarefas |
| Pede aprovação no que é sensível | ● | ● | ● |
| Atende clientes e passa para a pessoa quando precisa | — | — | ◐ em andamento |
| Relata o que fez e quanto custou | — | — | ◐ Atividade; falta custo por tarefa |
| Agenda, e-mail e documentos | ◐ por MCP | ◐ por plugins | ◐ por MCP; agenda do Omarchy |

## 5. Ordem sugerida

1. **Instalação de um comando, Linux e VPS** (seção 2). Sem ela, o resto não chega a ninguém.
2. **Pacotes** (E6, ADR 0033), para as integrações virem prontas.
3. **Conversar pelo WhatsApp**, que já está pareado, com o modelo de segurança dos canais.
4. **Fila durável com entrega verificável**: retomar depois de reiniciar e entregar num canal.
5. **Custo por tarefa** e relatório do que foi feito.
6. **Execução isolada** de conectores e comandos (contêiner).

## Fontes

Consultadas em 15/10/2026.

- Hermes: [README](https://github.com/NousResearch/hermes-agent/blob/main/README.md),
  [documentação](https://hermes-agent.nousresearch.com/docs/),
  [funções](https://hermes-agent.nousresearch.com/docs/user-guide/features/overview),
  [instalação](https://hermes-agent.nousresearch.com/docs/getting-started/installation).
- OpenClaw: [README](https://github.com/openclaw/openclaw/blob/main/README.md),
  [documentação](https://docs.openclaw.ai), [funções](https://docs.openclaw.ai/concepts/features),
  [ferramentas](https://docs.openclaw.ai/tools), [MCP](https://docs.openclaw.ai/tools/mcp),
  [instalação](https://docs.openclaw.ai/install), [gateway](https://docs.openclaw.ai/gateway).
