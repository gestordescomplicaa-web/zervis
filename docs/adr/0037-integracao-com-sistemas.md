# 0037 — Integração com sistemas: um método, não um catálogo de integrações

- Data: 19/10/2026
- Status: **Aceito** (pedido da pessoa em 17/10/2026: "o melhor não é deixar MCPs ou APIs
  prontas, como uma integração, mas sim fazer ele seguir uma regra documentada para pesquisar o
  passo a passo até a efetividade").

## Contexto

O Zé é usado por quem trabalha com automação e IA nos próprios projetos e nos de clientes. Grande
parte desse trabalho é ligar sistemas: CRM, ERP, planilhas, a API de um cliente. Hoje:

- O Zé já tem conectores MCP (`jarvis/cerebro/mcp_externo.py`, `conectores.py`): local ou remoto,
  segredos 0600 fora do arquivo, "Testar" e política por ferramenta (livre, aprovação, bloqueada).
  Mas só pelo painel: o cérebro não consegue cadastrar um conector.
- O Claude Code e o Codex sabem falar MCP e ler skills, mas não sabem *como trabalhamos aqui*:
  onde a chave fica, o que conta como pronto, o que fica bloqueado. Cada integração sai diferente.
- As sessões de código não recebem os conectores do Zé: o agente que constrói a automação do
  cliente não enxerga o sistema do cliente.
- MCPs remotos oficiais (Notion, Linear, Atlassian e outros) pedem login OAuth; o Zé só aceita
  cabeçalho fixo.

Um catálogo de integrações prontas envelhece rápido, não cobre o sistema do cliente e repete o
que os fornecedores já publicam como MCP. O que falta é o método e as peças que o deixam rodar
sem a pessoa intervir no meio.

## Decisão

1. **O método é uma skill**, `integrar-sistema` (`jarvis/habilidades/iniciais/`): entender o
   objetivo, pesquisar (MCP oficial, registro de MCPs, documentação da API), escolher o caminho
   (conector MCP, MCP próprio ou API direta), credenciais com o menor acesso e só pelo nome,
   provar com uma leitura real, decidir a política de cada ferramenta e registrar o aprendido
   numa skill do sistema. Vai também para as sessões (`sessoes: sim`): o Claude Code e o Codex
   leem a mesma regra pelas pastas de skills do projeto. Não é redundante com o harness deles:
   a skill não ensina a programar nem a usar MCP, só as decisões e provas da casa.
2. **O cérebro cadastra conectores** pelas ferramentas `conectores_listar` e `conector_testar`
   (livres) e `conector_cadastrar` (aprovação falada, com o comando ou o endereço na frase).
   Segredo nunca passa pelo cérebro: ele dá os nomes das variáveis e a pessoa guarda o valor no
   painel. Valor de segredo nos argumentos ou no endereço é recusado, venha do painel ou da
   conversa. O conector novo aparece como pendente no painel até "Aplicar agora".
3. **Conectores nas sessões de código, por projeto.** Cada conector diz em que projetos vale
   (`projetos`, nomes das pastas; `*` em todos). A sessão daquele projeto recebe o conector com
   os segredos já resolvidos, sem que eles apareçam na linha de comando: o Claude por um arquivo
   de configuração 0600, o Codex pelas variáveis do processo (`env_vars`, `env_http_headers`).
   Um conector sem `projetos` fica só na conversa com o Zé (separação entre clientes).
   Nas sessões, as ferramentas bloqueadas nunca chegam e as livres passam sem pergunta. As que
   pedem aprovação só valem no terminal do Claude, que pergunta na tela; sem terminal, ou no
   Codex (que não pergunta ao Zé antes de usar uma ferramenta MCP), ficam de fora.
4. **Login OAuth nos MCPs remotos, pelo Zé.** O painel faz o login (descoberta pelo próprio
   servidor MCP, registro dinâmico do cliente, PKCE) e guarda os tokens 0600. Uma ponte local
   (`127.0.0.1`, com segredo próprio) entrega cada pedido ao servidor com o token em dia e
   renova sozinha quando ele vence: o cérebro e as sessões não precisam recomeçar a cada hora.
   O mesmo login vale para o Claude, o Codex e qualquer outro provedor. Servidores que não
   aceitam o registro dinâmico do cliente (e exigem um app cadastrado à mão no fornecedor) usam
   o **app próprio**: o Client ID e o secret ficam num arquivo 0600 ao lado dos tokens e valem
   no lugar do registro; o secret vai no corpo do pedido ou em `Authorization: Basic`, conforme o
   que o servidor declara aceitar. A pessoa os informa nos detalhes do conector, nunca ao cérebro.

## Consequências

- A skill é sugerida como as outras iniciais: vale depois de instalada pela pessoa (Skills).
- O conector criado pela conversa só vale na conversa depois de aplicado (o cérebro recomeça).
- Os agentes rodam como o mesmo usuário do Zé e conseguem ler os segredos no disco. A regra
  proíbe repetir ou copiar segredo; isolamento de verdade exigiria outro usuário ou contêiner.
- O cérebro Claude ainda recebe os conectores pela linha de comando do SDK (`--mcp-config` em
  JSON), com os segredos stdio visíveis a outros processos do mesmo usuário. Fica como próximo
  passo levar o cérebro para o mesmo arquivo 0600 das sessões.
- A volta do login OAuth (`/oauth/retorno`) é a única rota do painel aberta sem cookie: ela só
  aceita um `state` de uso único, criado pelo painel há menos de 10 minutos, e o código só vale
  com o verificador PKCE que nunca sai do Zé.

## Andamento

- 19/10/2026: skill `integrar-sistema`, ferramentas de conectores no cérebro e pendência
  calculada no painel; conectores nas sessões por projeto; login OAuth com a ponte local.
  Descoberta conferida nos MCPs reais do Notion e do Linear (o Notion barra o User-Agent
  padrão do Python; o Zé se identifica como `Ze/1 (Zervis)`). O login completo, com a pessoa
  no navegador, ainda precisa da prova na máquina real.
- 19/10/2026: colar a configuração do serviço (JSON do MCP ou curl) em Conectores. O projeto
  escolhe os conectores dentro da sessão ("Conectores", na criação e no topo), e o vínculo passa
  a ser pelo caminho completo da pasta (o nome sozinho continua valendo para os antigos). O MCP
  do n8n conectou na máquina real.
- 19/10/2026: conector ligado a projeto sai da conversa com o Zé e fica só nas sessões do
  projeto ("Também na conversa" o traz de volta); a conversa acha a sessão pelos conectores de
  cada uma. As chamadas a MCPs externos pela conversa entram na Atividade.
