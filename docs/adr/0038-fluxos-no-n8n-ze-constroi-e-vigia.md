# 0038 — Fluxos dos clientes: o n8n executa, o Zé constrói e vigia

- Data: 19/10/2026
- Status: **Aceito como direção** (conversa de 19/10/2026). Cada etapa do plano é feita, provada e
  registrada antes da próxima. O aviso no WhatsApp de quem usa (etapa F3) cria um canal novo e
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
  | Activepieces | MCP próprio (cerca de 30 ferramentas: construir, testar, ver e refazer execuções) | Sim (MIT; Projetos e Git pagos) | Plano B open source. |
  | Windmill | MCP expõe scripts e fluxos prontos e os jobs; construir é editar arquivos e `wmill sync` | Sim (AGPLv3) | Para integração que é código. |
  | Kestra | MCP do OSS só chama fluxos marcados como ferramenta; construir é YAML pelo `kestractl` | Sim (Apache 2.0) | Orquestração de dados, fora do perfil. |

- **Licença do n8n** (FAQ oficial): é permitido construir, rodar e manter fluxos de vários
  clientes numa instância própria e cobrar por isso. É proibido revender o n8n com outra marca e
  deixar usuários finais montarem fluxos pelo seu produto. O Zé não embute o n8n: conecta-se ao
  n8n de quem usa ou do cliente.

## Decisão

1. **O Zé não executa fluxos de cliente.** O motor é o n8n (no começo), rodando fora do Zé: na
   VPS de quem usa (Docker) ou na instância do cliente. O executor de scripts próprio, proposto
   na primeira versão deste ADR, fica descartado.
2. **Cada n8n é um conector do Zé**, pelo que o ADR 0037 já entrega:
   - O MCP próprio do n8n (`/mcp-server/http`) é cadastrado colando o JSON que o n8n mostra, e
     vale **só no projeto daquele cliente**, ligado pelo botão "Conectores" da sessão (pelo
     caminho da pasta). Assim, a sessão do cliente A nunca enxerga o n8n do cliente B.
   - Para construir, a LLM da sessão (Claude ou Codex) usa as ferramentas do n8n: `search_nodes`,
     `get_node_types`, `get_workflow_best_practices`, as ferramentas de criar e atualizar fluxos,
     `test_workflow` e `publish_workflow`. O dono liga o MCP na instância e marca cada fluxo
     como "Available in MCP".
   - **Cada cliente, a sua versão.** Construir pelo MCP pede a 2.12 ou mais nova; a 2.36 tem tudo
     o que a skill usa (testar com dados de exemplo na 2.15, buscar execuções na 2.20, histórico
     e volta de versão na 2.29, diferença entre versões na 2.36). A sessão segue as ferramentas
     que aquele n8n mostra, e a skill diz o que fazer sem cada uma (26/10/2026).
   - **Um n8n, ou um usuário do n8n, por cliente.** O MCP do n8n separa por usuário, não por
     cliente: todo cliente MCP conectado com o mesmo usuário vê os mesmos fluxos.
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
4. **Publicar e mexer em produção pede aprovação.** A skill manda; o conector garante:
   `publish_workflow`, `unpublish_workflow` e `execute_workflow` ficam em "pede aprovação". Uma
   política pronta que já marca as leituras como livres ficou para depois (decisão da pessoa,
   19/10/2026). Enquanto isso, o n8n fica nas sessões do Claude: no Codex, as ferramentas em
   aprovação não chegam (ADR 0037).
5. **O vigia só responde a uma pergunta: o n8n está de pé?** (escopo pedido pela pessoa em
   19/10/2026). Erros de fluxo, credenciais e correções ficam com ela, nas sessões de construção.
   - Todo conector cujo endereço termina em `/mcp-server/http` é um n8n e é vigiado sozinho, sem
     configuração nova: do endereço sai a base, e dela `/healthz` (o processo responde) e
     `/healthz/readiness` (o banco responde). Os dois são abertos, sem chave (conferido numa
     instância real). Conector desligado não é vigiado.
   - Uma consulta por minuto, sem modelo e sem tokens, com tempo limite curto.
   - **Fora do ar** depois de 3 falhas seguidas (cerca de 3 minutos, para não alarmar numa
     oscilação), com o motivo em uma palavra: "sem resposta" (rede, DNS, VPS caída), "erro do
     servidor" (HTTP 5xx ou resposta errada) ou "banco fora" (`/healthz` ok e `readiness` não).
   - **Voltou** na primeira resposta boa depois de um "fora do ar".
   - Um aviso por mudança de estado, nunca um por minuto. O estado fica em SQLite, para um
     reinício do Zé não repetir nem perder o aviso.
6. **Avisos:** na central de avisos (falado conforme as regras de fala) e na Atividade
   (essência, item 6), com frases fixas: "n8n-joao fora do ar: sem resposta." e
   "n8n-joao voltou.". O aviso no WhatsApp de quem usa é uma peça nova, para depois.
7. **Onde roda:** em todo Zé, mas é o da VPS que vigia 24 horas. Se o n8n e o Zé dividem a mesma
   VPS e ela cai, ninguém avisa: para isso, o Zé do PC vigiando o da VPS, ou um ping externo,
   numa etapa futura.

## O que não fazer

- Motor de fluxos, nós ou fila de execução de cliente dentro do Zé.
- Passar pelo modelo nas consultas do vigia.
- Um conector de n8n valendo para todos os projetos (`*`): cada cliente, o seu.
- Dois clientes no mesmo n8n com o mesmo usuário do MCP: as duas sessões veriam os mesmos fluxos.
- A LLM criar credenciais ou ver segredos do n8n.

## Consequências

- O que roda nos clientes é o n8n, conhecido e auditável na tela por quem usa e pelo cliente. O
  fluxo é entregável: se o cliente sair, leva o n8n dele.
- O vigia não pede nada: colou o n8n em Conectores, ele já é vigiado.
- O vigia não vê fluxo com erro nem fluxo que deixou de rodar. Se a pessoa precisar, a próxima
  peça é ler as execuções pela API REST do n8n (com uma chave por instância) ou receber o aviso
  do nó Error Trigger por um webhook (rota aberta, zona protegida); cada uma com ADR curto.
- Cada cliente precisa de um n8n novo o bastante para o MCP: a 2.12 para construir, a 2.36 para
  o ciclo completo. Num n8n mais antigo, a sessão diz o que falta e segue o caminho da skill.
- Os agentes rodam como o mesmo usuário do Zé (ADR 0037): a separação entre clientes vem dos
  conectores por projeto, não de isolamento do sistema operacional.

## Plano

| Etapa | Escopo | Pronto quando |
|---|---|---|
| F1 | n8n como conector (colar o JSON), ligado na sessão do projeto, e a skill `fluxos-n8n`. | Numa sessão do projeto de um cliente, a LLM cria um fluxo num n8n real. A sessão de outro projeto não vê aquele n8n. |
| F2 | Vigia de saúde: `/healthz` e `readiness` de cada conector n8n, estado em SQLite, avisos na central e na Atividade. | Um n8n parado vira um aviso "fora do ar" com o motivo, e um só; a volta avisa; um reinício do Zé não repete o aviso; prova num n8n real. |
| F3 | Aviso no WhatsApp de quem usa (com a pessoa revisando). | O "fora do ar" chega no WhatsApp do número configurado. |

## Andamento

- 19/10/2026: F1 provada na máquina real: o JSON do n8n colado em Conectores, ligado na sessão
  pelo botão "Conectores", e uma sessão do Claude criou um fluxo no n8n. Skill `fluxos-n8n`
  (PR #24), com os nomes das ferramentas conferidos na instância.
- 19/10/2026: F2 (PR #25, `zervis/sistema/vigia_n8n.py`) provada pela pessoa: o n8n derrubado
  na VPS virou "fora do ar", e a volta, "voltou".
- 26/10/2026: reavaliação do motor (n8n, Activepieces, Windmill e Kestra, pela documentação
  oficial e pelo código). O n8n continua: o harness já é independente do motor nos conectores,
  na política e no vínculo por projeto, e só o vigia e a skill são do n8n; o MCP do n8n é o
  único com o ciclo inteiro do agente (validar, testar com dados de exemplo, execução por nó,
  diferença e volta de versão). Reabrir a escolha só com um gatilho: vender uma plataforma em
  que o cliente monta fluxos ou com outra marca (a licença do n8n proíbe: Activepieces ou
  Kestra); processos pesados de dados (Kestra ou Windmill ao lado); integração que é
  basicamente código (Windmill ao lado); ou o MCP do n8n regredir (Activepieces). A skill passou
  a seguir a versão de cada n8n (PR #44).
