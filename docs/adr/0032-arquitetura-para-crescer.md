# 0032 — Arquitetura para crescer: linguagem por papel, núcleo dividido, SQLite e pacotes

- Data: 14/10/2026
- Status: **Aceito como direção**. Cada etapa abaixo é feita, verificada e registrada aqui antes
  da próxima. Este documento é também o plano de trabalho: quem for executar (pessoa ou IA) lê
  inteiro antes de começar.

## Contexto

O Zérvis cresceu rápido: 177 commits entre 09 e 14/10/2026. Medido em 14/10/2026:

| Parte | Linhas |
|---|---|
| Python (`jarvis/`, sem o WaCalls) | ~28.000 |
| Testes (`tests/`) | ~14.000, 859 testes |
| JavaScript do painel e do imersivo | ~5.000 |
| Go (`jarvis/atendimento/wacalls/`, quase todo de terceiros) | ~18.000 |

A disciplina está boa (`make check`: formatação, lint, mypy estrito, testes e testes do Go). O
risco está em outro lugar:

- **Quatro arquivos viraram o centro de tudo:**
  - `jarvis/nucleo/laco.py` (2.724 linhas, a classe `Nucleo` com ~139 métodos);
  - `jarvis/oficina/sessoes.py` (1.573);
  - `jarvis/portal/acoes.py` (1.485, ~122 métodos numa classe só);
  - `jarvis/nucleo/estados.py` (1.364).

  Toda função nova encosta neles.
- **Dados em arquivos soltos:** 47 módulos gravam JSON ou JSONL por conta própria. Não há busca,
  transação nem migração de formato, e dois processos (Zé e Central de Atendimento) escrevem nos
  mesmos arquivos.
- **Painel em JavaScript sem tipos:** `painel.js` tem ~1.400 linhas.
- **Ainda não está pronto para o usuário final:** a instalação tem passos manuais (Go, chaves,
  `make instalar`), o pacote ainda se chama `jarvis`, documentos antigos falam de JARVIS e Orca, e
  o repositório é privado e nunca teve versão publicada.

A pergunta da pessoa foi se a solução era trocar de linguagem. A medição de uma ligação real
(ADR 0031, itens 10 e 11) responde que não:

| Etapa | Tempo | Onde roda |
|---|---|---|
| Fechar o turno | 0,4 s | Deepgram, na rede |
| Modelo começar a responder | 1,7 a 5 s | Claude, na rede |
| Gerar a voz | 0,1 a 0,15 s | Piper (onnxruntime, C++) |
| Áudio do WhatsApp | tempo real | WaCalls (Go) |

O Python que liga as peças gasta milissegundos. Reescrever não traria velocidade; custaria meses
e o ecossistema de IA, que é Python primeiro.

## Decisões

1. **Uma linguagem por papel, sem reescrita:**

   | Papel | Linguagem |
   |---|---|
   | Núcleo, cérebro, agentes, voz, atendimento | **Python** (fica) |
   | Mídia e conexões pesadas (WhatsApp, chamadas) | **Go** (já é: WaCalls) |
   | Painel | **JavaScript com tipos do TypeScript** (decisão 5) |
   | Áudio pesado no navegador | Rust/WebAssembly **só se uma medição pedir** |

   Regra: uma peça só é reescrita noutra linguagem depois de uma medição mostrar que ela é o
   gargalo. Esta decisão e a regra entram em `docs/06-qualidade.md`.

2. **Fronteiras por processo e por API.** Peças que precisam ficar de pé sozinhas ou que falam com
   terceiros rodam em processo próprio, com API local e token. Já é assim com a Central de
   Atendimento, o WaCalls, o ai-memory e o LiveKit. Cada fronteira tem um contrato escrito (rotas,
   formato, erros). Assim qualquer peça pode mudar de linguagem depois sem mexer nas outras.

3. **Dados em SQLite** (biblioteca padrão, um arquivo, sem servidor para o usuário instalar; o
   Hermes faz o mesmo):
   - Um módulo só cuida do banco (`jarvis/dados/`): conexão, modo WAL (vários processos lendo e
     escrevendo), migrações numeradas e automáticas ao subir, cópia de segurança.
   - Um banco por área em `<dados>/` (por exemplo `atendente/atendimento.db`, `zervis.db`), para que um
     problema numa área não pare as outras e para a Central ter o dela.
   - Cada migração importa os arquivos antigos uma vez e os move para `<dados>/.antes-do-sqlite/`
     (nada se perde; voltar é possível).
   - Busca de texto (FTS5) onde houver conversa: atendimento, conversas do Zé, atividade.
   - Segredos (chaves, tokens) **continuam fora do banco**, em arquivos 0600 em `<config>/`.

4. **Núcleo dividido em serviços.** O `Nucleo` deixa de ser o dono de tudo e vira o montador:
   cria os serviços, liga os eventos entre eles e roda o laço da voz. Os serviços (voz, cérebro,
   oficina/sessões, avisos, memória, foco, automações, acesso remoto, atendimento) têm interface
   pequena e testável sozinha. O painel deixa de falar com o `Nucleo` inteiro: `acoes.py` vira um
   pacote com um módulo por página (`jarvis/portal/acoes/atendimento.py`, `sessoes.py` e assim
   por diante), cada um recebendo só os serviços de que precisa.

5. **Painel tipado sem etapa de build.** O painel continua sem framework e sem nada de fora, mas
   ganha tipos em comentários JSDoc, conferidos pelo `tsc` (`checkJs`) no `make check`. O
   `painel.js` é dividido em módulos por página (como já são as páginas sob demanda em
   `paginas/`). Um framework leve (Preact ou Lit) só entra se a interface pedir, com ADR próprio.

6. **Extensões são pacotes, não código dentro do Zé.** O Zé já tem as duas peças: skills
   (`SKILL.md`, padrão agentskills.io) e conectores MCP (processo separado, permissão por
   ferramenta). Um **pacote** é uma pasta ou repositório Git com um manifesto que junta skills,
   conectores MCP e configurações. Ao instalar, o Zé mostra o que ele pede, e a pessoa aprova.
   - O formato segue o dos plugins do Claude Code e do Codex (`plugin.json`: skills, servidores
     MCP, comandos), que o Hermes também aceita. Assim os pacotes que já existem funcionam no Zé.
   - **Não** haverá plugin que rode código de terceiros dentro do processo do Zé, como no Hermes
     (`plugin.yaml` com ganchos no núcleo; a maquinaria dele tem mais de 40 arquivos). Isso
     contraria a essência (segurança acima da conveniência).
   - O mesmo mecanismo dá ações ao agente de atendimento (exemplo: um pacote "Agenda Google" dá
     ao agente "marcar horário" por MCP), sempre na lista de ações liberadas uma a uma.
   - Escada antes de crescer o núcleo (adaptada do Hermes): skill → conector MCP → pacote →
     função nova no núcleo, por último.

7. **Pronto para o usuário final:** instalar com um comando, configurar pela tela e pronto.
   Binários de terceiros (WaCalls, cloudflared, ai-memory) baixados prontos e conferidos por
   SHA-256, sem exigir Go nem compilador.

## Plano de execução

Uma etapa por vez, na ordem. Cada etapa termina com `make check` passando, o comportamento
conferido de verdade (não só teste com falsos) e uma linha de resultado aqui, na seção
"Andamento". Nada de dado pessoal no código (o teste `tests/test_usuario.py` vigia, inclusive em
`.go`). As regras de `CLAUDE.md`, `docs/06-qualidade.md` e `docs/essencia.md` valem em tudo.

### E1. Banco de dados do Atendimento (SQLite)
- **Por que primeiro:** é a área mais "banco de dados" e a única com dois processos escrevendo
  (o Zé e a Central).
- **Escopo:** criar `jarvis/dados/` (conexão, WAL, migrações, cópia de segurança). Levar para
  `<dados>/atendente/atendimento.db`: conversas por contato (hoje `atendente/conversas/*.jsonl`), contatos
  com o atendimento (hoje `pausados.json`), ligações (desfecho, duração), eventos para o Zé e
  busca FTS5 nas conversas. Os ajustes (`agente.json`) e a versão publicada (`publicado/`)
  continuam como arquivos: são configuração, não registro.
- **Arquivos:** `jarvis/atendimento/agente.py` (`Registros`), `central.py`, `ligacao.py`,
  `jarvis/portal/acoes.py` (Memória), testes de `tests/test_atendente.py` e
  `tests/test_central_atendimento.py`.
- **Pronto quando:** a migração importa as conversas existentes; o Zé e a Central, juntos,
  escrevem e leem sem perda; o cartão Memória mostra a mesma contagem; apagar a memória limpa o
  banco; um teste prova dois processos escrevendo ao mesmo tempo.

### E2. Dividir as ações do painel por página
- **Escopo:** `jarvis/portal/acoes.py` vira o pacote `jarvis/portal/acoes/`, com um módulo por
  página e um registro que monta `leituras()` e `escritas()`. Comportamento idêntico; nenhuma
  rota muda de nome.
- **Pronto quando:** `make check` passa sem mudar testes de comportamento; nenhum módulo passa de
  ~400 linhas; as rotas são as mesmas (um teste compara a lista antes e depois).

### E3. Dividir o núcleo em serviços
- **Escopo:** extrair do `Nucleo` (`jarvis/nucleo/laco.py`) os serviços com dono claro, um por
  vez, cada um num commit próprio: atendimento (cliente da Central e eventos), acesso remoto
  (túnel, senha, voz remota), avisos (mensagens, central de avisos), oficina (sessões,
  manutenção), cérebro (motores, contas, via rápida), voz (escuta, fala, ativação). O `Nucleo`
  fica com a montagem e o laço.
- **Pronto quando:** `laco.py` fica abaixo de ~1.000 linhas; cada serviço tem teste próprio sem
  subir o `Nucleo`; o serviço do Zé reinicia na máquina e a voz, o painel e o atendimento
  funcionam (prova real, não só testes).

### E4. SQLite nas outras áreas
- **Escopo:** na ordem, atividade (`jarvis/atividade.py`), conversas e linha do tempo da memória
  (`jarvis/memoria/conversas.py`, `linha.py`), sessões (`jarvis/oficina/sessoes.py`), automações
  (`jarvis/automacoes/jobs.py`), consumo (`jarvis/cerebro/consumo.py`). Cada uma com migração
  automática e busca onde fizer sentido. Estado volátil da tela (`rosto/`, `imersivo/`, `voz/`)
  continua em arquivo.
- **Pronto quando:** cada área migrada sobe a partir dos arquivos antigos sem perda, e a página
  correspondente mostra o mesmo conteúdo.

### E5. Painel tipado e em módulos
- **Escopo:** `tsconfig.json` com `checkJs` e `noEmit`; tipos JSDoc nas funções de
  `painel.js` e das páginas; o `tsc` entra no `make check` (sem build: o navegador continua
  recebendo os mesmos arquivos). Dividir `painel.js` em módulos por página, respeitando o teste
  de peso da abertura (`tests/test_portal.py::test_os_arquivos_da_pagina_sao_leves`).
- **Pronto quando:** `make check` roda o `tsc` sem erros; nenhuma mudança visível; o painel abre
  no Chromium sem erro no console.

### E6. Pacotes de extensão
- **Escopo:** ADR próprio com o formato do manifesto (compatível com `plugin.json` do Claude
  Code), instalação a partir de pasta ou Git, tela de aprovação (o que o pacote pede), versão
  fixada por commit, remoção. Os conectores MCP e as skills que já existem passam a poder vir de
  um pacote. O agente de atendimento recebe ações de pacotes pela lista de ações liberadas.
- **Pronto quando:** um pacote de exemplo (uma skill e um conector MCP) instala pela tela,
  aparece em Skills e Conectores, é removido sem rastro, e um pacote no formato do Claude Code é
  aceito.

### E7. Pronto para o público
- **Escopo:**
  - instalação de um comando (Linux);
  - binário do WaCalls publicado por versão (x86-64 e arm64), baixado e conferido por SHA-256,
    no lugar da compilação com o Go;
  - pacote `jarvis` renomeado para `zervis` (e as variáveis `JARVIS_*`), com aliases durante a
    transição;
  - revisão dos documentos antigos (visão, conceitos, reaproveitamento, plano da oficina);
  - README para quem chega;
  - CI no GitHub rodando o `make check`.
- **Antes de tornar o repositório público:** o histórico do Git tem dados pessoais removidos só
  daqui em diante. Números de telefone reais vindos dos testes do Ligatia estão no commit
  `7b1f787` e foram trocados no `9014b4a`. A decisão é da pessoa: reescrever o histórico ou
  publicar a partir de um commit novo, sem histórico.
- **Pronto quando:** uma máquina Linux limpa instala, configura pela tela e atende uma mensagem e
  uma ligação no WhatsApp, sem passo manual.

## O que não fazer

- Reescrever peças noutra linguagem sem medição.
- Plugin que rode código de terceiros dentro do Zé.
- Banco com servidor (Postgres) para quem instala sozinho.
- Mudar duas etapas ao mesmo tempo, ou mudar comportamento numa etapa de reorganização
  (E2, E3, E5 são reorganização pura).
- Mexer na zona protegida (essência, segurança, o que o Zé faz sem perguntar) sem a pessoa
  revisar.

## Andamento

| Etapa | Estado | Resultado |
|---|---|---|
| E1 | Concluído | SQLite privado com WAL, migrações transacionais, cópia consistente, importação recuperável, FTS5, contatos pausados, ligações e eventos persistentes. Prova com dois processos: 100 mensagens sem perda. API HTTP local aprovada; make check: 864 testes e Go aprovados. |
| E2 | Concluído | Dez módulos por página, registro compatível, dependências limitadas e contrato tipado. Maior módulo: 254 linhas. Rotas comparadas com o contrato anterior; make check: 866 testes e Go aprovados. |
| E3 | Concluído | Nove serviços com contextos e interfaces tipados; laço com 977 linhas. Testes de cada serviço sem Nucleo; make check: 877 testes e Go aprovados. Instância isolada no systemd subiu e reiniciou, painel HTTP 200, Central em processo próprio e Piper gerou 61.440 amostras reais. |
| E4 | Concluído | Atividade, conversas, linha do tempo, sessões, automações e consumo em SQLite, com importação dos formatos existentes. Buscas FTS5 e transações aninhadas; regressões de migração, rollback e dois processos escrevendo agendamentos e consumo. make check: 880 testes e Go aprovados; systemd isolado confirmou pelas APIs uma sessão, uma automação, duas falas e três respostas importadas, antes e depois do reinício. |
| E5 | Concluído | `tsc` com `checkJs` e `noEmit` no make check, sem build. `painel.js` de 1.460 para 131 linhas, dividido em seis módulos e quinze páginas; terminal e páginas carregam sob demanda. make check: 881 testes, tsc e Go aprovados; check-imersivo: 13 testes no Chromium. Passeio pelas 15 páginas no Chromium, versão anterior e nova com os mesmos dados: mesmo texto e nenhum erro novo no console. |
| E6 | Adiada | Depois da liberação (roteiro, MVP de 15/10/2026). Proposta em ADR 0033. |
| E7 | ⬜ | Absorvida pelas etapas 3 e 5 do MVP no roteiro. |

### Publicação

Em 14/10/2026, a pessoa escolheu criar um repositório público novo, sem o histórico antigo,
mantendo o repositório atual privado. Nenhum histórico existente será reescrito.

### Migração de registros

As raízes de dados guardam os bancos por área. Originais importados vão para `.antes-do-sqlite/`
ao lado do arquivo antigo; os arquivos atuais de configuração, anexos, código e eventos dos
agentes continuam nos seus lugares. Na atualização, os serviços antigos devem encerrar antes da
primeira subida da versão com SQLite, para nenhum escritor antigo continuar gravando JSONL.
