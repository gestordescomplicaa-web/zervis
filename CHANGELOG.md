# Mudanças

## Não lançado

- Endereço fixo do acesso de qualquer lugar, num domínio da pessoa no Cloudflare (Voz → Acesso de
  qualquer lugar → "Usar um endereço fixo"): cola-se o comando que o Cloudflare mostra ao criar o
  túnel e digita-se o endereço. O token vai para `~/.config/zervis/tunel-token` (0600) e o
  `cloudflared` o lê pelo `--token-file`, nunca na linha de comando. O Zé confere se o endereço
  chega mesmo ao painel e, se não, diz o que ajustar no Cloudflare. "Voltar ao automático" retorna
  ao endereço que muda a cada reinício. É a base do app de voz e das notificações do celular.
- Excluir uma sessão com cópia isolada: os atalhos `zervis-*` que o próprio Zé põe na cópia (as
  skills marcadas para as sessões, em `.claude/skills` e `.agents/skills`) saem antes da
  conferência. Antes, só eles, ignorados pelo Git, travavam a exclusão com "A cópia isolada tem
  alterações", e o "Descartar" da cópia não resolvia, porque preserva os arquivos ignorados.
- Atualizações pelo painel (Ajustes → Atualizações): o Zé procura uma vez por dia e só avisa
  (bolinha no menu e um aviso); "Atualizar agora" mostra o que muda, tirado do CHANGELOG, e roda o
  mesmo `zervis update` numa unidade própria do systemd (`zervis-atualizar`), fora do Zé, que
  reinicia no meio. Se a versão nova não subir, ele volta sozinho para a anterior. O painel
  recarrega quando o Zé volta, mostra o resultado, e o Zé avisa uma vez. O canal é "Versões
  publicadas" (padrão) ou "Desenvolvimento". Não atualiza com uma sessão trabalhando nem durante
  o autodesenvolvimento. Pela voz, "tem atualização?" responde (ferramenta `atualizacoes_ver`, só
  leitura); atualizar é no painel.
- Porta do painel: o `zervis` (`status`, `doctor` e a espera do `update`), o `make instalar` e o
  instalador passam a ler a porta que o systemd dá ao serviço, contando os ajustes em
  `zervis.service.d`, e a reinstalação sem porta mantém a que já está em uso. Antes, com a
  porta num ajuste, o `update` esperava o painel na porta errada e voltava para a versão
  anterior sem motivo, e o atalho do menu abria uma porta vazia.
- Nota do dia, revisão das conversas e automações: com a chave da Anthropic do painel recusada
  (sem crédito ou inválida) e o login da assinatura do Claude disponível, a consulta roda de
  novo pela assinatura, fica registrada uma vez na Atividade e as próximas vão direto. Antes, a
  chave sem crédito parou a nota do dia e a revisão por dias, enquanto a conversa (pelo Codex)
  seguia normal; as notas que faltam são escritas na próxima manhã, a partir das conversas.
- Testes do terminal no painel: esperam a conexão em tempo real desistir antes de digitar (eram
  instáveis na CI).

- O pacote se chama `zervis` (era `jarvis`): `python -m zervis`, `from zervis import …`, a pasta
  `zervis/`. As instalações de antes continuam subindo: a unidade antiga (`python -m jarvis`) e
  a Central antiga (`python -m jarvis.atendimento`) repassam para o `zervis` até o próximo
  `make instalar`, que grava a unidade nova. Os dados, a trava do serviço e os nomes que o
  cérebro usa (o servidor MCP `jarvis`, o alvo de memória `jarvis`) não mudam.

- Variáveis: `ZERVIS_PAINEL_PORTA`, `ZERVIS_PERFIL`, `ZERVIS_RAIZ`, `ZERVIS_FUSO` e
  `ZERVIS_PONTE_API_KEY` são os nomes; os `JARVIS_*` de antes continuam valendo quando o novo não
  existe (as unidades já instaladas têm `JARVIS_PAINEL_PORTA`). O instalador e o atalho gravam o
  nome novo.

- Nome: o assistente é o Zé em toda parte do código, da interface, das descrições das
  ferramentas e dos documentos atuais (eram 268 "JARVIS"); a persona passa a ser `ZE.md` (o
  caminho antigo continua como link) e o prefixo dos pedidos de manutenção, `[Zé · modo
  manutenção · pedido <id>]`. "Hey Orca" vira "Ei Zé" nos textos. ADRs, CHANGELOG e auditorias
  ficam como foram escritos. Os nomes técnicos (o pacote `jarvis`, as variáveis `JARVIS_*`, o
  arquivo de memória `JARVIS.md`) mudam depois, com transição.
- Dados expostos: uma imagem do avatar levava nos metadados o caminho do arquivo de origem, com
  o usuário da máquina; o fuso de quem desenvolve saiu de uma auditoria. O teste de dados
  pessoais passa a olhar também `.toml`, `.sh` e os metadados das imagens PNG.
- Documentos: o registro do serviço é `journalctl --user -u zervis` (estava `jarvisd`, que não
  existe), e a arquitetura antiga ganha o aviso do que mudou.

- Bateria de avaliação do cérebro (`zervis avaliar`, `docs/avaliacao.md`): cenários em TOML com
  o pedido, o que as ferramentas respondem e o que se espera (ferramentas, argumentos e
  resposta); o cérebro de verdade com as ferramentas simuladas, repetições para a taxa de
  acerto, relatório comparado com a rodada anterior e rodadas sem resposta fora da nota.
  Referência de 20/10/2026: 91% em 11 cenários.
- Conversas: a fala de quem usa passa a ser gravada como `pessoa`. Antes, a chave era o nome de
  uma pessoa, no código público. As conversas já gravadas continuam legíveis, sem migração, e o
  teste de dados pessoais passa a procurar sem distinguir maiúsculas.

## 0.1.0 (19/10/2026)

A primeira versão publicada. Destaques:

- **Instalação:** no PC (`deploy/instalar-pc.sh`) e na VPS (`deploy/instalar-servidor.sh`, com
  HTTPS, senha e código do autenticador), e o comando `zervis` (`status`, `doctor`, `update`,
  `logs`, `abrir`, `uninstall`). O `update` segue as versões publicadas e volta sozinho se o
  painel não subir.
- **Voz:** "Ei Zé" treinado com a voz de quem usa, interrupção, fim de turno pela entonação e voz
  local (Piper, Cadu), pelo PC ou pelo navegador do celular.
- **Oficina:** sessões Claude Code e Codex num terminal real, com cópia isolada, troca de conta
  sem perder a conversa e os conectores do projeto.
- **Integrações:** conectores MCP colados do serviço (JSON ou curl), login OAuth, permissão por
  ferramenta, separação por cliente; skills `integrar-sistema` e `fluxos-n8n`; vigia do n8n.
- **Memória, skills, automações, Foco e central de avisos**, com aprovação no que é sensível e
  tudo registrado na Atividade.
- **Controle da máquina** no Omarchy, com nível de risco por ação.
- **Atendimento no WhatsApp**, em teste.

O registro completo, item por item:

- Instalador do PC (`deploy/instalar-pc.sh`): serviço do usuário, atalho no menu e o painel aberto
  na configuração inicial, com o Go verificado para o WhatsApp.
- Comando `zervis`: `status`, `doctor` (cada função disponível ou não, com o motivo e como
  resolver), `update` (avança só um caminho limpo e volta sozinho se o painel não subir), `logs`,
  `abrir` e `uninstall` (os dados ficam, a não ser com `--apagar-dados` e a frase de confirmação).
- Conversa com o Zé: o conector ligado a um projeto (o n8n de um cliente) passa a valer só nas
  sessões daquele projeto, e a conversa recebe só os conectores gerais. Antes, todos iam para a
  conversa: pela voz, o Zé usava o n8n sem dizer de qual cliente, e as ferramentas de todos
  custavam tokens em todo turno. A chave "Também na conversa", no cartão, traz um de volta.
- O Zé acha a sessão certa: `sessoes_listar` mostra os conectores de cada sessão. Pergunta sobre
  o n8n com uma sessão ligada a ele vai para ela; com mais de uma, o Zé pergunta qual.
- Atividade: as ferramentas dos conectores MCP usadas pela conversa (Claude e Codex) passam a
  ser registradas, como as do próprio Zé (essência, item 6).
- `conectores_listar` traz o estado do vigia em cada n8n (de pé ou fora do ar), e o lembrete
  avisa ao cérebro que não confere nada: "quando o n8n voltar, me avise" não vira mais um
  lembrete repetido a cada 5 minutos, porque o vigia já avisa.
- Vigia do n8n (ADR 0038): todo conector do MCP de um n8n é vigiado sozinho, uma vez por minuto,
  pelo `/healthz` e pelo `/healthz/readiness` da instância, sem chave e sem modelo. Depois de três
  falhas seguidas, o aviso "<n8n> fora do ar: sem resposta" (ou "erro do servidor", "banco fora")
  vai para a tela e para a Atividade, e é falado conforme o modo de fala; a volta avisa
  "<n8n> voltou". Um aviso por mudança, guardado em SQLite: reiniciar o Zé não repete.
- Skill inicial `fluxos-n8n` (ADR 0038), também nas sessões: criar, editar, testar, publicar e
  investigar fluxos pelo MCP do n8n, na ordem que ele pede (boas práticas, tipos dos nós,
  validação, criação, teste com dados de exemplo). Produção só muda com aprovação; editar guarda
  a versão para voltar; todo fluxo publicado tem um fluxo de erro; credenciais só no n8n.
  A `integrar-sistema` aponta para ela e passa a mandar ligar o conector pelo botão da sessão.
- Sessões: o botão "Conectores", no topo da sessão (e a lista na criação), liga e desliga os MCPs
  do projeto ali mesmo. A escolha vale para todas as sessões daquela pasta; cada conector mostra
  em que outros projetos ele já está ("Também em: …"), e salvar reabre o agente com a conversa.
- Conectores por projeto pelo caminho completo da pasta: dois clientes com pastas de mesmo nome
  em lugares diferentes não se misturam. O nome sozinho, como era antes, continua valendo.
- Conectores: etiqueta "MCP" em cada cartão; "Nome" no formulário de colar, e colar o mesmo JSON
  para outro cliente pede outro nome em vez de sobrescrever. Os projetos saíram do formulário e
  do cartão (lá, só leitura): quem escolhe é a sessão.
- Conectores: "Adicionar" agora pede só para colar a configuração que o serviço fornece, o JSON
  do MCP (`mcpServers`, como o do n8n, do Claude ou do Cursor) ou o comando `curl`, e os
  projetos. "Salvar e testar" cria o conector, guarda tokens e chaves como segredos (nunca no
  arquivo de configuração), testa e mostra as ferramentas na hora. Colar de novo num conector
  existente ("Editar") troca a configuração e mantém as permissões. Os campos ficam em
  "Preencher campos", para quem precisar.
- Conectores: uma linha de cabeçalho fora do formato (`Authorization: N8N_AUTH`) era descartada
  sem aviso, e o conector ficava sem o cabeçalho (no n8n, HTTP 401). Agora o painel avisa
  "Cabeçalho inválido" e não salva; o valor pode ter `:` depois do primeiro. O token colado no
  lugar do nome da variável é recusado sem ser repetido na mensagem. O campo mostra o exemplo.
- Conectores: "Editar" no cartão abre o formulário com o que está gravado (endereço, cabeçalhos,
  segredos, projetos); os segredos guardados e as permissões continuam. Antes só dava para
  remover, o que apagava também os segredos.
- Conectores: "Ferramentas" com HTTP 401 ou 403 mostra "Acesso negado" e, quando o
  `Authorization` está sem o tipo (o token sem `Bearer `, como pede o n8n), diz isso, sem
  mostrar o segredo.
- Skill `integrar-sistema`: numa sessão de código, o agente não instala o conector por conta
  própria (`claude mcp add`, `.mcp.json`): diz à pessoa para pedir ao Zé ou cadastrar em
  Conectores, com o projeto marcado. Quem já instalou a skill atualiza o texto em Skills.
- Integração com sistemas (ADR 0037): a skill inicial `integrar-sistema` traz o método (pesquisar,
  escolher entre MCP e API, credenciais só pelo nome, provar com uma leitura real, registrar o que
  aprendeu) e vale também nas sessões de código. O Zé lista, cadastra (com aprovação) e testa
  conectores pela conversa; o painel mostra o conector novo como pendente. Valor de segredo nos
  argumentos ou no endereço de um conector é recusado.
- Conectores nas sessões de código: cada conector diz em que projetos vale (nome da pasta, ou
  `*`), e as sessões do Claude e do Codex daquele projeto o recebem com os segredos fora da linha
  de comando. Sem projetos, o conector fica só na conversa (o sistema de um cliente não aparece no
  projeto de outro).
- Conectores com login (OAuth): um MCP remoto que pede login (Notion, Linear e outros) entra
  com "Entrar" no cartão do conector, no navegador, sem chave. O Zé guarda os tokens (0600) e uma
  ponte local os renova sozinha, sem recomeçar a conversa nem as sessões. Fora do PC, a volta do
  login chega pelo endereço do painel; se não chegar, cola-se o endereço em que o navegador parou.
- Conectores com login: "Entrar" abre direto a aba de login do fornecedor, sem passo escondido;
  quando o login termina, a aba fecha (ou leva de volta ao painel) e o cartão passa a
  "Conectado" sozinho. Se o navegador bloquear a nova aba, aparece o botão "Abrir login".
- Conectores com login: servidores que não aceitam o registro automático do cliente passam a
  funcionar com um app próprio. O Client ID (e o secret, se houver) é guardado nos detalhes do
  conector (0600, nunca devolvido) e o cartão mostra o endereço de retorno a cadastrar no app;
  o secret segue no corpo do pedido ou em `Authorization: Basic`, como o servidor pedir.
- Servidor (VPS): primeiro acesso sem túnel SSH. O instalador termina com um endereço HTTPS
  (Cloudflare) e um código de uso único para criar a senha; num servidor, quem entra com a senha
  e o código do autenticador faz os ajustes de fora (chaves, contas, autodesenvolvimento), menos
  desligar as proteções. Com só a senha, o endereço continua de pé depois de um reinício.
- Acesso pelo celular: um túnel que ficou de pé sem o endereço anotado (reinstalação) sobe de
  novo, em vez de falhar.
- Código aberto: CONTRIBUTING, SECURITY, CODEOWNERS, modelo de PR e o ADR 0036 (contribuições
  por pull request, `master` protegida, atualização de quem personaliza o Zé em aberto); o guia
  de VPS passa a clonar o repositório público e explica o acesso sem o túnel SSH.
- Voz ao vivo: o que se diz enquanto o Zé pensa não é ouvido, e agora isso aparece na Atividade
  ("Fala não ouvida enquanto o Zé pensava"); buracos no áudio do navegador (rede, tela apagada)
  vão para o registro do serviço.
- Sessões: a sessão nova pelo painel começa no agente que tem conta conectada (antes, sempre
  no Claude), e o Zé cria a sessão numa pasta nova a pedido, sem mandar a pessoa ao painel.
- Painel: a troca de aba mostra na hora o que a página já tinha e se atualiza quando o Zé
  responde; longe do servidor (VPS), cada aba deixa de esperar uma ida e volta de rede. Gravar
  qualquer ajuste invalida o que estava guardado.
- Servidor (VPS): o autodesenvolvimento abre num Zé instalado de um pacote. O instalador cria o
  histórico Git local que a cópia isolada exige, e sem ele o painel diz o que fazer em vez de
  "não foi possível unificar pelo Git".
- Escuta: quando o Deepgram recusa a conexão, o registro e a Atividade dizem o motivo (chave,
  crédito, limite, e a explicação do próprio Deepgram), e uma recusa passageira, inclusive o 401
  intermitente, tenta de novo uma vez sem perder o que foi dito.
- Sessões por voz: cada sessão nova ganha a própria pasta em `~/projetos`, sem precisar dizer o
  caminho; o agente padrão é o que tem conta conectada. Projeto novo numa máquina sem nome no git
  já sai com o primeiro commit.
- Cérebro Codex: as ferramentas do Zé (sessões, lembretes, memória) funcionam com os modelos
  novos do Codex. O Zé baixa, junto com o Codex, o auxiliar que executa essas ferramentas.
- Sessões: a lista de pastas sugeridas não repete as pastas de `~/projetos`.
- Contas: "Entrar" faz o login do Claude Code e do Codex pelo próprio painel (link e código na
  tela), sem terminal na máquina: funciona numa VPS e pelo celular.
- Agentes: o Claude Code e o Codex vêm com o Zé (o Codex oficial, conferido por SHA-256); o
  Codex aceita a chave da OpenAI pelo painel, inclusive a mesma das Respostas rápidas.
- Modelos de som: o download tenta primeiro o espelho do projeto (`ZE_MODELOS_URL`) e cai para a
  fonte original, sempre conferindo o SHA-256; `deploy/publicar-modelos.sh` publica os modelos
  numa release do GitHub, para a voz Cadu não depender de uma única fonte.
- Servidor (VPS): `deploy/instalar-servidor.sh` instala o Zé como serviço que continua depois
  de sair do SSH; guia em `docs/vps.md`. O Zé sobe sem áudio na máquina (a voz chega pelo
  navegador) e sem os modelos de som que não baixaram (painel e texto funcionam).
- O cérebro sabe em que máquina está (Omarchy, outro Linux ou servidor) e, fora do Omarchy,
  não oferece suspender o computador.
- Sessões de código funcionam sem o Claude Code instalado à parte: usam o que vem com o Zé.
- Sessões: excluir uma sessão não trava mais num contêiner sem init (Docker sem `--init`), onde
  os processos encerrados do agente ficavam como zumbis.
- Qualidade: a CI do GitHub roda o `make check` completo a cada envio, com o painel num Chromium
  de verdade, os modelos de som e o Go; teste pulado conta como falha.
- Autodesenvolvimento: a unificação reconhece rascunhos já reconciliados na central e evita
  repetir o mesmo conflito a cada tentativa; conteúdo ou base novos continuam sendo conferidos.

- Autodesenvolvimento: sessão central independente de conta, agente e modelo, com recuperação
  persistente e bloqueio de duplicações. O painel unifica cópias antigas preservando commits,
  rascunhos, histórico e pendências; conflitos interrompem a migração e as origens ficam guardadas.

- Sessões: um evento de conclusão repetido não registra outra resposta nem dispara um segundo aviso.

- Sessões por voz: confirmação curta pelo nome, com o prompt completo no envio e destino fixado
  antes do sim. Cada resultado inclui um resumo em Normal e Mãos livres; várias sessões avisam
  separadamente, sem exigir "próximo". O resumo preserva pendências e tem alternativa sem modelo.

- Atualização: novos pedidos e teclas do terminal ficam bloqueados desde a aprovação até o
  resultado, inclusive no autodesenvolvimento. Conversas e saídas continuam disponíveis para
  leitura; falha ou cancelamento liberam o envio e preservam tarefas pendentes.

- Autodesenvolvimento: trocar Claude, Codex ou conta mantém a mesma sessão, a cópia e os pedidos.
  O limite semanal é reconhecido mesmo quando o aviso chega em partes. Interromper, com
  confirmação, encerra o agente preservando a conversa e libera a troca; a atualização bloqueia
  essas operações enquanto estiver em andamento.

- Atualização: andamento visível em todas as páginas, com etapas, tempo decorrido e estimativa.
  O resultado continua visível depois do reinício; falhas e retorno à versão anterior aparecem
  na tela. Pedidos repetidos não iniciam outra aplicação.

- Atendimento (ADR 0031): página nova para conectar um número de WhatsApp ao Zé pelo QR. Com os
  avisos de lead quente ligados, as mensagens desse número passam a ser a fonte dos avisos, sem
  precisar do WhatsApp aberto no computador. É a base do atendente no WhatsApp e nas ligações
  (docs/plano-atendente.md). Requer o Go na primeira conexão.
- Atendimento: o agente que responde clientes no WhatsApp, separado do Zé, com persona própria
  (nome, empresa, como atender, o que sabe, quando passar para você), Testar sem enviar, modo
  teste só para números escolhidos e a lista "Com você" das conversas passadas para você.
- Atendimento: o agente virou um projeto (`~/projetos/agente-de-atendimento`) com README,
  persona, conhecimento e testes de conversa. "Abrir sessão" cria uma sessão de código nele, e
  "Publicar" só coloca a versão nova para os clientes com todos os testes passando.
- Atendimento: página revista, com um cartão por função. Interruptores claros para responder no
  WhatsApp e atender ligações; o cérebro em destaque, com as chaves de API (Salvar, Testar,
  Remover) na própria página; e o cartão Memória, que mostra o que o agente guarda e apaga.
- Atendimento: nas ligações, o agente fala como numa ligação (as regras de fala do Ligatia),
  sem abreviação ("oito horas", "cento e cinquenta reais") e sem frase de bastidor. Pré-aquecimento,
  geração antecipada e uma reação curta ("Uhum.") enquanto o modelo pensa. A página Atendimento
  mostra e deixa escolher o cérebro do agente; com chave de API, as ligações respondem mais rápido.
- Atendimento: o agente atende ligações do WhatsApp em tempo real (opção "Ligações do WhatsApp"
  no cartão Agente): ouve pelo Deepgram, responde com a mesma persona e fala com a voz do Cadu.
  O cliente pode interromper; quando precisa de você, ele avisa que alguém retorna e encerra.
- Atendimento: o agente só responde em conversa privada. Grupos, status e canais ficam de fora,
  com três travas independentes.
- Atendimento: a Central de Atendimento roda num serviço próprio (`zervis-atendimento`).
  Reiniciar o Zé, inclusive para aplicar melhorias, não derruba mais o WhatsApp nem o agente.
- Avisos do WhatsApp: o Zé lê as notificações do WhatsApp deste computador e avisa só de lead
  quente (quem quer comprar ou mostra interesse real). Desligado por padrão; liga em Voz > WhatsApp ou dizendo
  "liga os avisos do WhatsApp". Nunca responde nem abre a conversa.
- Voz: o Zé não corta mais quem pausa para pensar. Frase que termina pela metade ("e", "que",
  "pra", vírgula) espera o silêncio longo, e a nova escolha Espera (Rápida, Normal, Longa) na
  página Voz define as pausas; Normal espera 1 s em vez de 0,64 s.
- Acesso pelo celular: o túnel roda num serviço próprio; reiniciar o Zé não troca mais o endereço
  (e o celular não pede login de novo). O endereço só muda quando o computador reinicia.
- Confirmação por voz: uma pergunta que demora a tocar (pelo celular) não expira antes de dar
  tempo de responder, e um "sim" atrasado não trava mais o Zé.
- Tarefa interrompida: se o Zé reinicia no meio de um pedido a uma sessão, ele avisa e oferece
  continuar de onde parou (pela voz ou pela faixa na sessão).
- Sessões: o × do topo virou o botão "Excluir", com a confirmação numa faixa abaixo do cabeçalho.
- Autodesenvolvimento: a autorização de ferramentas do Codex também é zona protegida.
- Automações: criação e alteração simultâneas preservam os agendamentos; temporários exclusivos.
- Sessões: Aplicar e Descartar para cópias isoladas, com prévia, confirmação e falhas Git verificadas.
- Sessões: o modelo de cada sessão se escolhe no cabeçalho dela, com a versão; a conversa continua.
- Skills: só as marcadas "Também nas sessões de código" vão para os agentes de código; as outras
  valem só para o Zé.
- Skills: o editor virou formulário (Nome, Quando usar, Do meu jeito, Passos, Pronto quando); o
  arquivo é montado por trás, e "Editar como texto" continua disponível.
- Skills: a página mostra também as skills já instaladas no Claude Code e no Codex (só leitura).
- Memória: cartão "Memória dos projetos" com o estado do ai-memory e quantas páginas ele guarda.
- Memória: o que muda no meio da conversa (painel, aprovação, voz) vale já no próximo pedido.
- Memória: as sugestões que o Zé aprende numa conversa aparecem no painel, com Aprovar e Descartar.
- OmniRoute no painel: Cérebro → OmniRoute, com o endereço e a chave do OmniRoute de quem usa
  (local por http ou num servidor por https) e a lista de modelos dele; também nas Respostas rápidas.
- Respostas rápidas: o modelo vem da lista com a versão (Claude, Codex, Anthropic); o Codex do
  cérebro mostra "Padrão da conta" quando não há modelo escolhido.
- Modelos: o modelo do cérebro se escolhe no painel (a mesma lista das sessões) e vale na hora;
  "Voz rápida" passa a se chamar "Respostas rápidas" e fica junto do Cérebro.
- O modo de fala "Avisos" passa a se chamar "Normal" ("modo avisos" por voz continua valendo).
- Chamado universal: o "Ei Zé" vem treinado no repositório, com vozes sintéticas, e funciona para
  qualquer pessoa sem gravar a própria voz. A gravação pessoal virou ajuste opcional.
- O chamado ignora silêncio e som de fundo: precisa de volume de alguém falando ao microfone
  (configurável em `ativacao.nivel_minimo_dbfs`).
- Silencioso trava o microfone: nem "Ei Zé", nem o botão, nem o Ao vivo; a conversa é pela tela.
- O Zé tem a vez: enquanto ouve, pensa ou fala, vídeo e música (navegador e players) pausam e
  voltam depois. Chamado sem ninguém falar depois fecha a escuta em 6 s.
- "Repete" (ou "não entendi", "fala de novo") repete a última fala do Zé inteira, na hora.
- Central de avisos (ADR 0029): o Zé narra as sessões em vez de ler a resposta delas ("A sessão
  Loja terminou. Ela corrigiu o login."), com um toque antes; aprovação e falha passam na frente;
  vários avisos viram uma oferta ("Duas novidades… Começo pela Site?") e a pessoa conduz com
  "começa", "próximo", "depois" e "o que ela disse?". A Conversa mostra o que espera.
- Conversa no painel: o fio do dia com o Zé (pedidos, respostas e avisos) e o campo para escrever.
  No Silencioso, o que o Zé não falou aparece também como notificação em qualquer página.
  Conectores passa a carregar só quando aberto.
- Revisão do painel: as sessões no terminal (Claude e Codex) passam a receber as skills do
  usuário, como a página promete. Reiniciar o Zé não registra mais "o túnel caiu" nem erros de
  conexão do painel; o diagnóstico ignora o encerramento normal do agente.
- Segurança: aplicar ou reiniciar o Zé só do próprio PC. A voz do celular e o texto digitado não
  aplicam, e a zona protegida nunca entra pela voz, só pelo painel com a revisão marcada.
- Manutenção é um estado do Zé (ADR 0028): liga por voz ou no Autodesenvolvimento, deixa o
  painel em laranja, e só nele valem Diagnosticar e Aplicar. Aplicar espera as sessões de outros
  projetos terminarem, sem interromper ninguém.
- Reinício e atualização: o painel mostra "Reconectando…" e recarrega sozinho quando o Zé volta.
  A volta automática desiste em segundos quando a versão nova cai ao subir, e a cópia isolada
  volta a ficar igual ao Zé em uso. Volta testada de ponta a ponta (13/10/2026).
- A página Melhorias passa a se chamar Autodesenvolvimento, assim como a sessão do Zé.
- Imersão no PC só roda à vista: sair dela ou esconder o painel desliga a câmera e o holograma.
- Diagnóstico de uso: o túnel do acesso de fora sobe de novo sozinho quando cai e revoga o
  endereço antigo; a voz do navegador reconecta após queda de rede e separa "desligou" de "caiu";
  o modo imersivo guarda a própria saída e o vigia mostra o código de saída, sem chamar de queda
  a saída ordenada; escuta vazia fecha com o bip em vez de "não entendi"; o relatório agrupa cada
  erro não tratado pela exceção final e onde ela nasceu.
- Regras de fala (ADR 0027): aviso falado em no máximo 30 palavras, com o resto na tela; o fim
  da sessão de melhorias é uma frase; aviso cortado volta uma vez só; o mesmo aviso não se repete
  em 2 minutos.
- O Zé começa aqui como projeto aberto, para instalar do zero. Ele herda o núcleo já existente:
  voz (Deepgram e Piper), cérebro trocável, via rápida, memória curta e longa, skills, Foco,
  automações, sessões de agentes de código e o painel.
- Pastas de dados e serviços com o nome `zervis`, fuso do sistema, e nada de nome, caminho ou
  serviço de alguém fixo no código (um teste vigia isso).
- Licença AGPL-3. A voz vem junto: o Piper roda dentro do Zé e a voz Cadu é baixada e conferida
  na primeira subida. Primeiro som em ~150 ms (antes ~320 ms pelo serviço à parte).
- Configuração inicial no painel: sem perfil, o painel abre nela. Perfil (nome, sobre e fuso),
  acesso ao Claude (assinatura ou chave de API, com teste de conexão) e reconhecimento de fala.
  Perfil e acesso também ficam em Ajustes; mudanças valem sem reiniciar (o fuso, no próximo início).
- A chave do Deepgram colada no painel agora liga também a palavra de ativação, sem reiniciar.
- O modo imersivo agora é parte do Zé (ADR 0014): o holograma com as expressões e a boca que
  acompanha a voz, o Núcleo com os orbes e a tela movida pelas mãos vêm no repositório, e o Zé
  sobe o servidor junto com ele. Os testes da página rodam em `make check-imersivo`.
- Modo imersivo limpo para quem começa do zero: as esferas são Mapa, Hoje, Trabalho, Acervo e
  Guia, cada uma alimentada pelo próprio Zé e visível só quando tem conteúdo. Sem Orca nem lista
  de ferramentas no Mapa; medidores técnicos só no modo desenvolvedor (docs/imersivo/ESFERAS.md).
- O Acervo é a pasta do Zé nos dados de quem usa (`acervo/imagens` e `acervo/3d`), sem arquivos de
  exemplo; o orbe só aparece quando há imagem ou modelo 3D nela.
- Guia do modo imersivo em português, sobre o Zé: primeiros passos, gestos, atalhos, as esferas e
  os comandos de voz. Os atalhos de teclado também ficam no menu de configurações (tecla D), e o
  anel mostra o estado em português.
- Modelos em três camadas (ADR 0015): Voz rápida (conversa simples, em menos de um segundo),
  Cérebro (pedidos com ação; agente, com o acesso) e Sessões de código (agentes que continuam
  depois). O Codex aparece como próxima opção do cérebro e das sessões.
- O modo manutenção não depende mais do Orca: o Zé abre uma sessão própria de código no próprio
  repositório ("Zé · manutenção"), a reaproveita nas próximas vezes e fala o resumo do agente. A
  zona protegida, os testes e o reinício seguro continuam iguais.
- Acesso como no Orca: o Zé mostra os agentes instalados nesta máquina (Claude, Codex) e o login
  feito em cada um, sem fazer login de assinatura. Sai o campo de token da assinatura; a chave de
  API da Anthropic fica como alternativa.
- O Orca saiu do núcleo: o cérebro delega trabalho de código às sessões próprias do Zé pelas
  ferramentas `sessoes_listar`, `sessao_criar`, `sessao_enviar`, `sessao_ler` e `sessao_parar`
  (ler é livre; criar, mandar e parar pedem aprovação). Persona e arquitetura acompanham.
- O ai-memory vem embutido (ADR 0016): o Zé usa o da máquina ou baixa o binário oficial (versão
  e SHA-256 fixos) e o roda junto. As sessões de código do Zé alimentam a memória pelos hooks dele
  e, ao começar, recebem a passagem do que a sessão anterior fez no mesmo projeto.
- Contas dos agentes (ADR 0016): em Modelos, cada agente (Claude, Codex) lista as contas desta
  máquina com o login, o e-mail mascarado e o plano; dá para adicionar outra conta (uma pasta de
  login própria), entrar nela pelo próprio agente (o Zé abre o terminal), escolher a conta em uso
  e remover. O cérebro e as sessões usam a conta escolhida.
- O Codex é motor das sessões de código: ao criar uma sessão, escolhe-se Claude ou Codex; o Codex
  roda pelo `codex exec` na conta da sessão, escreve só na pasta do projeto e continua a mesma
  conversa nos pedidos seguintes. O cabeçalho da sessão mostra o agente e a conta.
- Troca de agente ou de conta no meio da sessão, sem perder a conversa (ADR 0016): na mesma
  agente, a conversa nativa vai para a conta nova e continua inteira; noutro agente, ele recebe a
  passagem do que já foi feito e, ao voltar, retoma a própria conversa com o que mudou. Botão
  Trocar na sessão, ferramenta `sessao_trocar` no cérebro e aviso quando a conta bate o limite.
- Créditos esgotados avisados na tela: quando a conta do agente bate o limite, a sessão mostra
  "Créditos esgotados" com botões "Continuar com <outra conta>", que trocam de conta e mandam de
  novo o pedido que ficou sem resposta. O agente e a conta da sessão se trocam ali mesmo, num
  seletor no cabeçalho.
- O ícone do Zé (o chimpanzé holográfico) no topo do menu lateral do painel e na aba do navegador;
  acende e pulsa quando o Zé está ativo.
- A sessão de código é o terminal real do agente (ADR 0017): o `claude` ou o `codex` rodando na
  pasta e na conta da sessão, com todos os comandos dele (`/model`, `/effort`, `/compact`...). O
  cabeçalho mantém agente e conta (a troca reabre o terminal sem perder a conversa), o aviso de
  créditos esgotados, os arquivos e os anexos (arrastar, colar ou "+": o caminho vai para o
  terminal). O que se digita e o que o agente responde continuam na conversa do Zé, para a
  passagem entre agentes e para o cérebro acompanhar.
- Trocar de agente não dispara mais um pedido automático: o resumo do que já foi feito entra como
  contexto do agente novo (ou fica no campo, junto com o próximo pedido), sem gastar um turno.
- Modos de fala (ADR 0018): Silencioso (nada falado, chamado desligado), Avisos (padrão: fim de
  sessão em uma frase, aprovação, créditos e erros) e Mãos livres (também a resposta da sessão,
  resumida para ouvir). Troca no menu lateral, na página Voz, com Alt+M ou por voz. O que está
  aberto na tela não é falado.
- Mãos livres de verdade: o Zé sabe de qual sessão se fala (a do último aviso, a aberta na tela
  ou pelo nome), e "diz pra ela rodar os testes" vai para ela; depois de um aviso de sessão ele já
  fica ouvindo a resposta, sem "Ei Zé"; "como está a Loja?" conta os comandos e os arquivos que o
  agente mexeu.
- Voz em qualquer Linux (ADR 0021): a escolha "Escuta" na página Voz, "Sempre" ou "Com a janela
  aberta" (esta só com Hyprland). Sem Hyprland o Zé escuta o chamado enquanto estiver rodando, e
  usa o microfone padrão do sistema quando o MIC FX do Omarchy não existe.
- Voz pelo navegador (plano da voz remota, etapa 1): o botão "Conectar voz" no menu lateral liga o
  microfone do navegador ao Zé por uma sala LiveKit que o próprio Zé baixa, confere e mantém, só
  no endereço local. Conectado, o microfone do PC fecha e a voz do Zé sai pelo navegador.
- Cérebro Codex voltou a subir: o Codex 0.162 recusava o nome do MCP entre aspas no `-c`.
- O chamado repetido ("Ei Zé" de novo, ou o "Eis é" que o Deepgram às vezes escreve) não vira mais
  "Não consegui entender": o Zé segue ouvindo, e o chamado sai do começo do pedido. Pela voz no
  navegador, a fala que começa durante o bip fica no pedido (o navegador já cancela o eco).
- Segurar para falar (ADR 0022): botão no menu lateral e espaço; segurar envia ao soltar, um toque
  começa e outro envia. Nova escolha "Ativação" na página Voz: "Ei Zé" ou Só o botão (no celular,
  o microfone só transmite com o botão apertado). O Silencioso agora só cala o Zé.
- Voz pelo navegador: uma reconexão deixava duas faixas de microfone escrevendo juntas e o Zé
  ouvia frases trocadas; agora vale só a mais recente.
- Voz ao vivo (ADR 0023): com a voz conectada o Zé ouve sem parar, sem "Ei Zé", até desconectar;
  silêncio, "ok" e ruído não encerram nem pedem repetição, e os avisos saem nas pausas. O botão de
  falar virou um pedido só: depois da resposta, o Zé espera o botão de novo.
- Menu lateral com grupos recolhíveis (Trabalho, O Zé, Ajustes), lembrados no navegador; o grupo
  da página aberta fica sempre aberto. A voz virou uma barra no rodapé do menu: modo de fala, Ao
  vivo e Falar. No celular, o menu vira uma barra no topo e o conteúdo não fica mais por baixo.
- O ícone do Zérvis no menu mostra o estado do Zé com animação: ondas ouvindo, brilho girando na
  borda pensando, pulso falando, âmbar esperando o "sim"; apagado quando inativo. O texto do estado
  saiu do menu (fica na dica do ícone), e o painel confere o estado a cada segundo.
- Acesso pelo celular (plano da voz remota, etapa 2): na página Voz, Ativar publica o painel e a
  sala de voz na rede privada do Tailscale (`tailscale serve`, HTTPS válido), e a mídia da voz passa
  a usar o endereço da máquina nessa rede. Nada fica aberto na internet.
- Voz pelo celular em casa: o Chrome do Android não manda o áudio pela VPN do Tailscale; o servidor
  de voz passa a oferecer também o endereço do PC na rede de casa, e o cartão "Acesso pelo celular"
  mostra o comando que libera o firewall só para essa rede. O registro do LiveKit fica em
  `livekit.log`, na pasta de estado.
- Senha de acesso (roteiro, passo 4.1): o próprio PC entra direto; qualquer outro aparelho passa
  pela tela Entrar, uma vez por aparelho ("lembrar este aparelho": 30 dias). A senha é guardada só
  como resumo (scrypt), cinco erros bloqueiam por 15 minutos, e trocar a senha ou "Encerrar
  acessos" desconecta todos. Ativar o acesso pelo celular exige a senha definida.
- Voz pelo HTTPS (ADR 0024): o Ao vivo do navegador manda o microfone e recebe a voz do Zé pelo
  WebSocket do próprio painel, sem WebRTC: onde o painel abre, a voz funciona, sem porta nem firewall.
  A tela fica ligada durante o ao vivo. O painel não carrega mais o cliente do LiveKit.
- Acesso de qualquer lugar sem nada no celular (roteiro, passo 4.3): em Voz > Acesso pelo celular,
  Ativar abre um túnel do Cloudflare que o Zé baixa e confere, e mostra o endereço e um QR; o
  celular abre no navegador, entra com a senha e fala pelo ao vivo, em casa ou no 4G. O painel vira
  app instalável (ícone na tela inicial). Pedido que chega por túnel ou proxy nunca vale como o
  próprio PC. O Tailscale fica como alternativa, só se estiver instalado.
- Segurança do acesso de fora: código do autenticador (verificação em duas etapas, TOTP) obrigatório
  para o acesso de qualquer lugar; bloqueio de tentativas por endereço de origem (quem ataca não
  tranca quem usa); aviso falado e na tela quando um aparelho entra, com a lista de aparelhos e
  Desconectar em cada um; ajustes de acesso (senha, código, túnel) só pelo próprio PC.
- Imersão no celular: em outro aparelho, a aba Imersão mostra o holograma do Zé em tela cheia,
  reagindo à conversa (ondas ouvindo, que crescem com a sua voz; brilho girando pensando; pulso no
  volume real da fala; âmbar esperando o "sim"), com Ao vivo e Falar grandes embaixo. A Imersão
  completa, com as mãos e o Núcleo, continua só no PC.
- Painel no celular refeito: barra no topo com o menu, menu deslizante com os grupos e a voz numa barra
  fixa embaixo (Fala, Ao vivo, Falar); em Sessões, uma coisa por vez (a lista ou a sessão, com
  "Sessões" para voltar) e o cabeçalho da sessão em duas linhas. Holograma em resolução cheia.
- Depois de reiniciar o computador, o Zé dizia que o Codex não estava instalado: o serviço sobe com
  um PATH mínimo, antes de a sessão carregar o ambiente da pessoa. Agora o Zé completa o PATH na
  subida com o do shell de login e as pastas pessoais de programas (~/.local/bin, mise, npm, bun…).
- Atividade (ADR 0025): tudo o que o Zé executa fica registrado, com o comando, como foi autorizado
  (livre, aprovado, frase exata), de onde veio o pedido e o resultado; também as negadas, as falhas,
  o que ele não entendeu (com o que ouviu), as correções e os pedidos atendidos. Nova página
  Atividade, com o registro técnico do serviço e "Copiar diagnóstico". Nova ação: suspender o
  computador (confirmação falada).
- Essência do Zé (`docs/essencia.md`, ADR 0026): o que ele é e não deixa de ser. A sessão de
  manutenção passa a ler a essência, só trabalha no próprio Zé (recusa o resto) e tem a zona
  protegida ampliada com a segurança nova (senha, túnel, atividade, WebSocket) e a persona.
- Sessão "Zé · melhorias" (ADR 0026, passo 2): fixa no topo de Sessões, trabalha numa cópia isolada
  do Zé (git worktree) e mostra o que mudou; "Aprovar e aplicar" roda os testes na cópia, junta ao
  Zé em uso e reinicia com o reinício seguro (zona protegida exige a revisão marcada; só pelo
  próprio PC); "Descartar" volta a cópia ao Zé em uso. "Reinicia o Zé" por voz também aplica.
- Página Melhorias (ADR 0025 e 0026): a sessão do Zé sai de Sessões e mora aqui, só no próprio PC.
  Diagnosticar monta o relatório do que deu errado (falhas, não entendi, correções, negadas e os
  erros que mais se repetem no registro técnico, agrupados por causa) e o entrega à sessão, que
  propõe as correções sem implementar até a pessoa escolher.
- Sessão de código aberta e fechada sem nenhum pedido não trava mais ao reabrir ("No conversation
  found"): o Zé só retoma conversas do Claude que existem e, se não existir, começa uma nova.
