# 0038 — Fluxos dos clientes: o n8n executa, o Zé constrói e vigia

- Data: 19/10/2026
- Status: **Aceito como direção** (conversa de 19/10/2026). Cada etapa do plano é feita, provada e
  registrada antes da próxima. O aviso no WhatsApp de quem usa (decisão 6) cria um canal novo e
  passa pela revisão da pessoa (essência, item 5).
- Complementa o [ADR 0037](0037-integracao-com-sistemas.md): ali, o Zé usa sistemas pelo MCP;
  aqui, o trabalho repetido dos clientes roda num motor de fluxos, e o Zé o constrói e vigia.

## Contexto

Quem usa o Zé atende empresas (PMEs): monta e mantém integrações entre os sistemas delas (CRM,
ERP, planilhas, WhatsApp). A pessoa dá o norte e o Zé faz o trabalho pesado. Ela não quer
acompanhar cliente por cliente: quer que um fluxo que caiu chegue até ela sozinho.

Pergunta da pessoa: construir no Zé um motor de fluxos próprio (nós de webhook, HTTP, IF, Switch,
fila), ou usar uma plataforma pronta com o Zé por trás?

O que se aprendeu na pesquisa e na conversa de 19/10/2026:

- **Rodar o trabalho repetido pelo modelo não serve.** Custa tokens a cada execução, demora e
  pode dar um resultado diferente a cada vez. No Hermes, cerca de 73% de cada chamada é custo fixo
  (ferramentas e prompt).
- **O Hermes tem um cron sem modelo** (`no_agent`), com webhook, novas tentativas e histórico.
  Ele serve para vigias e sinais de vida, mas não para fluxo de cliente: o script é um bloco só, as
  credenciais não são cuidadas e não há separação por cliente nem trabalhadores em fila.
- **Motor próprio no estilo do n8n:** o caro não são os nós, é o que fica embaixo deles (fila
  durável, novas tentativas por passo, credenciais com OAuth renovado, histórico com os dados de
  cada passo, editor). Seria um segundo produto.
- **Quem vigia não deve ser quem executa.** Se os fluxos rodassem dentro do Zé, uma queda dele
  derrubaria juntas a execução e a vigilância.
- **Plataformas comparadas** pelo que importa aqui: o agente construir por MCP, rodar na VPS de
  quem usa e ter API de execuções para o vigia.

  | Plataforma | Construir por MCP | Na VPS | Nota |
  |---|---|---|---|
  | **n8n** | MCP próprio: busca nós, cria, edita, testa com dados de exemplo, publica, histórico de versões e execuções. Há também o n8n-mcp (MIT) da comunidade, com documentação de nós e validação. | Sim | Escolhido. |
  | Make | Maduro, mas as ferramentas de criar e editar só existem nos planos pagos | Não | Motor futuro, se o cliente já usa. |
  | Zapier | "Next Gen Zaps" em acesso antecipado | Não | Caro por execução. |
  | Activepieces | MCP próprio (cerca de 30 ferramentas) | Sim (MIT) | Plano B open source. |
  | Kestra, Windmill | Documentação, YAML ou scripts | Sim | Orquestração de dados ou código, fora do perfil. |

- **Licença do n8n** (FAQ oficial): é permitido construir, rodar e manter fluxos de vários
  clientes numa instância própria e cobrar por isso. É proibido revender o n8n com outra marca e
  deixar usuários finais montarem fluxos pelo seu produto. O Zé não embute o n8n: conecta-se ao
  n8n de quem usa ou do cliente.

## Decisão

1. **O Zé não executa fluxos de cliente.** O motor é o n8n (no começo), rodando fora do Zé: na
   VPS de quem usa (Docker) ou na instância do cliente. O executor de scripts próprio, proposto
   na primeira versão deste ADR, fica descartado.
2. **Cada n8n é um conector do Zé**, pelo que o ADR 0037 já entrega:
   - O MCP próprio do n8n (`/mcp-server/http`) é cadastrado como conector remoto, com login OAuth
     ou chave, e vale **só para o projeto daquele cliente** (`projetos`). Assim, a sessão do
     cliente A nunca enxerga o n8n do cliente B.
   - Para construir, a LLM da sessão (Claude ou Codex) usa as ferramentas do n8n: `search_nodes`,
     `get_node_types`, `get_workflow_best_practices`, as ferramentas de criar e atualizar fluxos,
     `test_workflow` e `publish_workflow`. Versão recomendada: n8n 2.18.4 ou mais nova. O dono
     liga o MCP na instância e marca cada fluxo como "Available in MCP".
   - Para instância antiga, ou quando faltar documentação de nós e validação, entra o n8n-mcp da
     comunidade (MIT, pela API REST e uma chave), como conector local do mesmo projeto.
3. **O método é uma skill**, `fluxos-n8n` (inicial, `sessoes: sim`):
   - entender o pedido;
   - preferir nós nativos (o nó de código só para pequenas transformações, para o fluxo continuar
     legível);
   - credenciais criadas pela pessoa no n8n, nunca pela LLM;
   - testar com dados de exemplo;
   - um fluxo de erro ligado em todo fluxo publicado;
   - nunca editar um fluxo em produção direto: trabalhar numa cópia ou numa versão não publicada,
     comparar as versões e publicar só com aprovação.

   A skill `integrar-sistema` aponta para ela quando o caminho for "fluxo repetido".
4. **Publicar e mexer em produção pede aprovação.** O conector do n8n vem com `publish_workflow`,
   `unpublish_workflow` e `execute_workflow` em **aprovação**, e as leituras livres. Na sessão
   sem terminal e no Codex, as ferramentas de aprovação ficam de fora (regra do ADR 0037).
5. **O vigia roda sem modelo, no Zé da VPS:**
   - Um laço próprio, com o mesmo princípio do `no_agent` do Hermes, consulta cada motor
     cadastrado pela **API REST** (não pelo MCP: o MCP é para a LLM, e o vigia não gasta tokens).
     A cada 1 a 2 minutos:
     - se a instância responde;
     - quais execuções falharam desde a última consulta;
     - quais fluxos marcados como críticos não rodaram no horário esperado. "Não rodou" é a falha
       silenciosa mais perigosa.
   - O n8n também pode chamar o Zé na hora, com um fluxo de erro, mas isso é complemento: **se o
     n8n cai, ele não avisa ninguém**, por isso a consulta é obrigatória.
   - O estado fica em SQLite (ADR 0032): última consulta, falhas vistas e janela de cada fluxo.
   - **O modelo só entra quando algo quebra.** O Zé lê a execução que falhou e resume a causa
     provável (credencial vencida, API do cliente fora, campo que mudou, limite de uso), com a
     correção proposta. Corrigir é uma sessão de código do projeto daquele cliente, com
     aprovação.
6. **Avisos para quem usa:**
   - na central de avisos e na Atividade (essência, item 6);
   - no **WhatsApp de quem usa**, peça nova: hoje o WhatsApp do Zé só atende clientes e lê leads.
     É um envio só para um número configurado, com frases fixas e o resumo do vigia, nunca com
     dados do cliente além do necessário.
   - A primeira falha avisa e as repetidas não repetem o aviso. A volta ao normal também avisa.
7. **Página "Clientes"** (grupo Trabalho): um cartão por cliente, com estado ("Em dia", "Com
   falha", "Fora do ar"), motores, fluxos críticos, a última falha e **Abrir sessão** no projeto
   do cliente. É pensada também para o celular.
8. **Motores trocáveis.** O vigia e a página falam com uma interface pequena (`saude`,
   `execucoes_com_falha`, `ultima_execucao`, `fluxos`). O n8n é o primeiro motor. Make e
   Activepieces entram depois, cada um com ADR curto, onde a API deles der o que o vigia precisa
   (ainda não conferido).
9. **Onde roda:** os dois Zés constroem, mas **o vigia é do Zé da VPS**, porque está sempre
   ligado. O Zé do PC mostra o mesmo estado quando estiver conectado à VPS (ADR 0034).

## O que não fazer

- Motor de fluxos, nós ou fila de execução de cliente dentro do Zé.
- Vigiar só pelo aviso do n8n, sem consulta.
- Passar pelo modelo em cada consulta do vigia.
- Um conector de n8n valendo para todos os projetos (`*`): cada cliente, o seu.
- A LLM criar credenciais ou ver segredos do n8n.

## Consequências

- O que roda nos clientes é o n8n, conhecido e auditável na tela por quem usa e pelo cliente. O
  fluxo é entregável: se o cliente sair, leva o n8n dele.
- O Zé fica leve: o vigia são consultas HTTP, e dezenas de instâncias não pesam.
- Cada cliente precisa de um n8n novo o bastante para o MCP (2.18.4 recomendado). Instâncias
  antigas são vigiadas pela API e construídas pelo n8n-mcp da comunidade.
- O próprio Zé da VPS precisa de alguém de fora que o vigie: um ping externo simples que avise
  se ele parar (etapa F4).
- Os agentes rodam como o mesmo usuário do Zé (ADR 0037): a separação entre clientes vem dos
  conectores por projeto, não de isolamento do sistema operacional.

## Plano

| Etapa | Escopo | Pronto quando |
|---|---|---|
| F1 | n8n como conector por projeto: cadastro guiado (endereço, OAuth ou chave), política padrão (leituras livres; publicar e executar em aprovação), skill `fluxos-n8n`. | Numa sessão do projeto de um cliente, a LLM cria um fluxo num n8n real, testa com dados de exemplo e publica com aprovação. A sessão de outro projeto não vê aquele n8n. |
| F2 | Vigia sem modelo: cadastro de clientes e motores, consulta pela API REST, falhas novas, "não rodou", estado em SQLite, avisos na central e na Atividade. | Uma falha forçada num fluxo vira um aviso só; o n8n parado vira "Fora do ar"; um fluxo crítico que não rodou é detectado; o reinício do Zé não repete avisos. |
| F3 | Triagem pelo modelo e página "Clientes". | Uma falha real chega com causa e correção propostas; a página mostra todos os clientes, também no celular. |
| F4 | Aviso no WhatsApp de quem usa (com a pessoa revisando) e ping externo do próprio Zé. | A falha chega no WhatsApp do número configurado; o Zé da VPS parado é avisado por fora. |
