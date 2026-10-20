# Auditoria de maturidade: Zérvis, Hermes Agent e OpenClaw

Data de referência: 13/10/2026. Checkout: `aca2855`.

O Zérvis já é um assistente pessoal funcional, com uma arquitetura de agente consistente.
Minha nota geral é **7,4/10**. Para conversar e operar o próprio computador com supervisão,
está perto de **8/10**; para executar trabalho autônomo de longa duração, recuperar falhas e
ser instalado por qualquer pessoa, ainda fica atrás das capacidades documentadas de Hermes
Agent e OpenClaw. A maior necessidade agora é confiabilidade das operações existentes.

## Escopo e método

- Inventário de 123 módulos Python, aproximadamente 24.457 linhas, e 74 arquivos de testes
  Python na raiz de `tests`. JavaScript e componentes de terceiros não entram nesse total.
- Leitura aprofundada dos fluxos de cérebro, contas, ferramentas, sessões, memória, skills,
  automações, acesso remoto, autodesenvolvimento, persistência e instalação; revisão do
  checklist e das auditorias funcionais.
- `make check` executado neste checkout: **760 testes passaram**, com formatação, lint e tipos.
- `make check-imersivo`: **12 testes passaram em 96,36 s**, no Chromium sem tela, com
  entradas simuladas. Isso não substitui uma nova prova de microfone, câmera ou voz no celular.
- Serviço local consultado: ativo, sem erro de cérebro ou voz no status naquele momento.
- Duas reproduções controladas em diretórios temporários, sem agentes de modelo ou mudanças
  em projetos reais. Verificação adicional da lista de arquivos protegidos.
- Comparação com documentação e repositórios oficiais consultados na auditoria. Não executei
  Hermes ou OpenClaw nem apliquei o mesmo benchmark aos três: a comparação externa é de
  capacidades documentadas, não de taxa de sucesso comprovada.
- Há dois arquivos já modificados antes da auditoria: `jarvis/oficina/sessoes.py` e
  `jarvis/portal/acoes.py`. O fluxo novo de cópia isolada é trabalho incompleto e foi avaliado
  separadamente. A auditoria não altera esses arquivos nem aplica mudanças nos projetos.

Estas notas são julgamento de engenharia. Quantidade de testes não mede, por si só, sucesso
em tarefas reais, resistência a injeção de prompt ou recuperação de um processo interrompido.

## Notas por dimensão

| Dimensão | Peso | Nota | Evidência e limite |
|---|---:|---:|---|
| Entender pedidos e usar ferramentas | 20% | 8,5 | Interface Brain, políticas de aprovação, MCP e motores Claude/Codex; depende dos runtimes externos |
| Memória e skills | 20% | 8,0 | Memória curta, ai-memory, sugestões aprovadas e skills nas sessões; sem avaliação comparativa de aprendizado |
| Experiência de voz e uso diário | 15% | 8,0 | Ativação universal, Deepgram, Piper, navegador remoto e avisos; cauda de latência e casos sem som merecem análise |
| Confiabilidade operacional | 20% | 6,5 | Testes e reinício supervisionado; persistência sem transação completa e recuperação de tarefas limitada |
| Segurança e supervisão | 15% | 7,0 | Token, Host, senha/TOTP, política de risco, sandbox Codex; zona protegida incompleta e isolamento desigual |
| Distribuição e alcance | 10% | 5,5 | Pacote, systemd e painel remoto; falta instalação limpa validada, CI e canais mais amplos |
| **Média ponderada** | **100%** | **7,4** | Referência para priorização, não certificação de produção |

## Comparação com os projetos de referência

**Hermes Agent.** O projeto documenta criação e melhoria de skills, memória, delegação,
automações, canais de mensagens e diferentes ambientes de execução. O Zérvis já tem versões
funcionais de memória, skills, delegação e agendamento. A diferença está na abrangência dos
ambientes e na maturidade do ciclo operacional das tarefas. [Repositório oficial](https://github.com/NousResearch/hermes-agent).

A busca de sessões do Hermes usa SQLite e FTS5. O Zérvis tem essa capacidade por integração
com ai-memory; seus próprios registros de sessões e jobs continuam em JSON/JSONL. Integrar
uma biblioteca de memória é uma decisão válida, mas não resolve automaticamente a persistência
dos outros subsistemas. [Memória do Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory).

**OpenClaw.** O projeto documenta um gateway para sessões, ferramentas e canais, instalação
orientada, plugins e dispositivos. O Zérvis já possui um núcleo, painel e transportes locais/remotos,
mas não oferece o mesmo alcance de canais e plataformas. [Repositório oficial](https://github.com/openclaw/openclaw).

OpenClaw documenta sandbox configurável e regras de isolamento de conversa por remetente.
Isso também exige configuração: não seria correto assumir segurança perfeita ou isolamento
por padrão no concorrente. O Zérvis deve ser avaliado hoje como assistente de um único dono,
com vários aparelhos, e não como serviço que separa usuários mutuamente desconfiados.
[Sandbox](https://docs.openclaw.ai/gateway/sandboxing),
[sessões](https://docs.openclaw.ai/concepts/session).

| Capacidade | Zérvis atual | Distância para as referências |
|---|---|---|
| Conversa com ferramentas | Implementada nos dois cérebros | Pequena no uso pessoal supervisionado |
| Memória e skills | Implementadas e registradas como usadas | Falta medir recuperação correta e melhora após aprender |
| Delegação | Sessões nativas Claude/Codex e passagem de contexto | Falta contrato de tarefa, fila durável e validação de entrega |
| Automação | Lembretes e consultas agendadas | Falta unificar provedores, concorrência e recuperação de execução |
| Voz e interface própria | PC, navegador remoto e imersivo | Um foco de produto definido; superioridade não medida |
| Isolamento | Conversas separadas; worktree opcional | Não equivale a isolamento de sistema operacional |
| Instalação e canais | Linux, painel próprio e acesso pelo celular | Alcance e instalação ainda menos consolidados |

## Achados priorizados

### A1 — Alta prioridade: zona protegida incompleta no Codex

**Evidência:** `jarvis/oficina/manutencao.py:40` define `PROTEGIDOS`. Inclui `claude.py`,
`codex_rpc.py` e `codex_mcp.py`, mas não `codex.py`. A decisão de executar ferramentas está em
`CodexBrain._atender_codex`, em `jarvis/cerebro/codex.py:88`.

**Verificação:** aplicar o predicado de proteção aos caminhos retorna verdadeiro para
`claude.py` e `codex_mcp.py`, mas falso para `codex.py`. Não foi feita alteração nesse código.

**Implicação:** uma mudança na autorização do Codex pode deixar de exigir a revisão adicional
reservada à zona protegida. Ainda existe aprovação normal para aplicar melhorias; o problema
é a ausência dessa classificação mais rigorosa.

**Correção recomendada:** proteger o ponto de decisão do Codex e criar uma regressão que confira
os arquivos responsáveis por autorização, não apenas os caminhos já listados.

### A2 — Alta prioridade: gravações simultâneas de jobs podem perder dados

**Evidência:** `jarvis/automacoes/jobs.py:57`, `:64` e `:71`: criação lê a lista, acrescenta e
reescreve o arquivo inteiro. Não há lock cobrindo a operação completa; escritores usam o mesmo
`.next`. O painel tem threads e o agendador também atualiza jobs.

**Reprodução:** duas threads criaram lembretes num diretório temporário. Uma barreira foi
adicionada somente à leitura para forçar ambas a observar a mesma lista. Resultado: **um job
preservado de dois, e FileNotFoundError em uma escrita**.

**Implicação:** publicação atômica evita um arquivo pela metade, mas não evita atualização perdida
nem colisão do temporário. Não basta haver um único processo do serviço.

**Correção recomendada:** serializar todas as operações de leitura/modificação/gravação e usar
temporários exclusivos; depois migrar os registros mutáveis para armazenamento transacional.
SQLite do ai-memory não substitui essa necessidade.

### A3 — Alta prioridade antes de concluir o trabalho pendente: sucesso falso no descarte

**Estado:** achado no código ainda não commitado, não classificado como funcionalidade pronta.

**Evidência:** `jarvis/oficina/sessoes.py:903` e `:949`. Consultas Git usam `stdout` sem verificar
sucesso, e `reset`/`clean` não têm o retorno validado. O método devolve “Mudanças descartadas.”.

**Reprodução:** projeto Git e worktree temporários, com um arquivo modificado. O ponteiro `.git`
da cópia foi tornado inválido. `descartar_copia` retornou sucesso, mas **a alteração permaneceu**.

**Implicação:** a tela pode afirmar um resultado que não ocorreu. Os métodos novos também não
usam o lock de ciclo de vida já existente. Aplicar ou descartar deve falhar fechado e preservar
estado consistente quando a verificação, merge, reset ou limpeza falhar.

**Correção recomendada:** validar todos os retornos Git, serializar o ciclo de vida, definir o
tratamento de arquivos ignorados e concluir interface e testes com conflito, falha e execução
concorrente. Não habilitar a entrega como concluída apenas porque o merge comum funcionou.

### A4 — Prioridade média: terminar um turno ainda não prova entrega da tarefa

**Evidência:** `Sessoes._fim_do_turno` marca parada e registra um resumo após o evento de término.
Ao iniciar o serviço, uma sessão antes trabalhando vira parada com instrução para pedir de novo
(`jarvis/oficina/sessoes.py:174`).

**Implicação:** o sistema sabe que o agente respondeu ou encerrou, mas não tem um contrato geral
para validar objetivo, artefatos e critérios de aceitação. Não há uma fila durável de tarefas com
checkpoints e recuperação controlada. A volta automática do serviço não retoma o trabalho.

**Correção recomendada:** tarefa com estados explícitos, critérios de entrega e evidências. A
retomada precisa verificar o que já foi feito antes de repetir ações com efeitos externos.

### A5 — Prioridade média: o limite de três não cobre igualmente o terminal

**Evidência:** `Sessoes._enviar` verifica `MAXIMO_TRABALHANDO`; os endpoints de abrir e escrever
terminal em `jarvis/portal/acoes.py:1020` e `:1042` não passam por essa verificação. O hook de
pedido do agente marca trabalhando depois de receber o pedido.

**Implicação:** a regra protege o envio pelo Zérvis, mas não é uma garantia global para pedidos
digitados diretamente nos terminais. Esta conclusão vem do fluxo estático; não abri quatro
agentes reais nem consumi quatro contas para testá-la.

**Correção recomendada:** escolher entre garantir o limite nos terminais ou apresentá-lo como
limite da delegação do Zérvis. Se for garantia global, precisa de admissão também nesse caminho.

### A6 — Prioridade média: algumas consultas continuam dependendo de Claude

**Evidência:** `jarvis/automacoes/executor.py:19` e
`jarvis/habilidades/revisao.py:246` usam diretamente `claude_agent_sdk.query`. O agendador usa
`cfg['cerebro']['modelo']` e não o cérebro selecionado nem a camada de alternativas.

**Implicação:** selecionar Codex não migra automaticamente as consultas agendadas e a revisão de
aprendizado. A narração de sessões também tenta Claude, embora tenha uma alternativa local de
texto quando o resumo falha. O limite de uma conta pode afetar capacidades secundárias.

**Correção recomendada:** fábrica comum de consultas sem ferramentas, com escolha de conta,
classificação de erro, prazo e alternativas; manter as restrições das automações.

### A7 — Prioridade média: isolamento de arquivos e isolamento de segurança são diferentes

**Evidência:** sessão isolada é opcional; sessões comuns podem editar a mesma pasta. Codex usa
`workspace-write`, enquanto Claude usa `acceptEdits` no terminal. Memória e configuração de
contas podem ser compartilhadas.

**Implicação:** conversa separada e worktree reduzem colisões, mas não fornecem uma fronteira
uniforme de segurança entre agentes. Não há prova de confinamento equivalente no Claude e no
Codex. MCP externo também executa com as permissões do transporte/processo configurado.

**Correção recomendada:** documentar o que cada modo separa; para trabalho menos confiável,
definir sandbox com acessos explícitos a arquivos, rede e segredos. Uma instrução no prompt não
substitui essa fronteira.

### A8 — Prioridade média: consumo e sucesso ainda não são medidos integralmente

**Evidência:** `jarvis/cerebro/rapido.py` declara uso nos motores HTTP, mas não captura o usage do
fluxo. Os terminais das sessões também não alimentam o mesmo contador de consumo.

**Implicação:** o total exibido é parcial. Os testes automatizados não fornecem uma taxa de sucesso
em pedidos reais. Não é possível provar, hoje, que o Zérvis é mais eficiente que as referências.

**Correção recomendada:** registrar consumo por turno/modelo/conta e medir uma bateria de pedidos
com resultado verificável: sucesso, recuperação, latência e consumo. Começar com 30–50 cenários
representativos, repetidos em condições controladas.

### A9 — Prioridade média: distribuição e documentação ainda não acompanham o produto

**Evidência:** versão `0.0.1`, sem workflow de CI encontrado no checkout; dependências `livekit`
e `segno` com limites abertos, apesar da regra de versões exatas. O lock ajuda a reproduzir o
ambiente de desenvolvimento, mas não torna essas restrições do pacote exatas.

README e roteiro ainda deixam a ativação universal e várias funções remotas como pendentes,
enquanto o checklist registra uso real. A migração dos registros próprios para SQLite está
planejada, não implementada; as consultas SQLite encontradas são de integrações.

**Correção recomendada:** alinhar documentos ao código, validar instalação do zero em outra
máquina/distribuição, criar CI e estabelecer instalação, atualização e recuperação reproduzíveis.

## Evidência de desempenho local

Nos registros de 13/10 há 118 turnos: 94 concluídos, 13 de controle, 8 sem som, 2 interrompidos
e 1 serviço parado. Esses rótulos e esse uso misturam modos e testes: **não são uma taxa de
sucesso do agente**. Casos sem som precisam ser relacionados ao modo de fala antes de virarem
falhas de áudio.

Exemplos de grupos sem aprovação, do fim da fala ao primeiro PCM entregue:

- Claude rápido: mediana 2,94 s, p95 3,41 s, em 24 turnos concluídos de um mesmo grupo.
- Codex rápido: mediana 2,17 s, p95 2,20 s, em apenas três turnos concluídos.
- Cérebro Claude: mediana 2,60 s, p95 8,27 s, em 25 turnos concluídos de um mesmo grupo.

Os grupos têm condições diferentes e amostras pequenas. Não comparar modelos por esses números
nem confundir primeiro PCM com medição acústica. Há instrumentação útil; falta um benchmark
com tarefas e condições fixas.

## O que preservar

- A separação entre conversa rápida, cérebro e sessões de código.
- Aprovação determinística para ferramentas, frase de risco e varredura de memória/skills.
- Fallback somente antes de texto ou ferramenta: evita repetir efeitos externos.
- Dados XDG, instância única, arquivos sensíveis restritos e checksums dos modelos baixados.
- Memória curta acessível, aprendizado aprovado e skills explicitamente destinadas às sessões.
- Supervisão do autodesenvolvimento, cópia isolada e recuperação de atualização do serviço.
- Voz brasileira, interação local, navegador remoto e identidade visual própria.

## Sequência recomendada

1. Fechar A1 e A2; concluir o fluxo pendente A3 com provas de preservação de dados.
2. Fechar a auditoria funcional de sessões e tornar explícitas as garantias de limite e isolamento.
3. Unificar as consultas em segundo plano e criar tarefas com entrega verificável e recuperação.
4. Completar observabilidade, avaliação de pedidos e consumo; melhorar os gargalos medidos.
5. Validar instalação limpa, alinhar documentação e automatizar checks antes de ampliar canais.

Mais integrações aumentariam a abrangência, mas não corrigiriam as falhas operacionais encontradas.
O Zérvis tem uma base boa para o objetivo pessoal; a próxima etapa deve tornar essa base previsível.

## Correções após a auditoria

A1 e A2 corrigidos: autorização do Codex protegida; operações de agendamentos serializadas com
temporários exclusivos. A3 concluído com prévia e confirmação no painel, retornos Git verificados,
serialização do ciclo de vida, bloqueio durante execução e preservação de ignorados. O fluxo
genérico não permite aplicar cópias do autodesenvolvimento sem a revisão própria.

As reproduções passaram a ser testes de regressão. O Chromium confirmou Aplicar e Descartar pela
API real em projetos temporários, após a confirmação na tela. Os demais achados continuam como
próximas etapas; esta correção não constitui nova avaliação da nota geral.

Validação das correções: `make check` aprovado com 781 testes; teste específico do painel
no Chromium aprovado. Serviço reiniciado e conferido, com sessões preservadas.
