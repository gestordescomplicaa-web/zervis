# Plano de maturidade

Data: 06/11/2026. Nasceu de uma análise de CTO que comparou o Zérvis com Hermes Agent, OpenClaw,
Grok Bot e Meta Muse. Nota atual **6,4/10 como produto**; meta **7,8**, sem perder o que o Zérvis
já faz melhor que todos: voz e condução de sessões de código.

Regra durante as Fases A e B: **funções novas congeladas**. Entram correções e o que as frentes
pedem. Cada item feito é marcado aqui no mesmo PR que o entrega.

Revisão de 11/11/2026, conferida no código depois da 0.5.0: nota **7,2** (o plano previa ≈ 7,5 ao
fim da Fase B). O que falta para os 7,5 está em
[Fecho da Fase B](#fecho-da-fase-b-revisão-de-11112026), e fecha antes da Fase C.

Regra da Fase C: as funções novas voltaram (a abertura, ADR 0078). **Função nova entra com o teste
dela na porta de qualidade** (a que roda na CI) e só depois do fecho da Fase B. A abertura levou
oito PRs num dia (#153 a #166), cinco deles corrigindo o que só apareceu no uso real, porque os
testes da Imersão não rodam na CI.

## Placar

| Critério | Peso | 06/11 | 11/11 | Meta | Frente |
|---|---:|---:|---:|---:|---|
| Arquitetura e engenharia | 20% | 7,5 | 8,3 | 8,5 | 5 |
| Proposta e diferencial | 15% | 8,0 | 8,2 | 8,5 | 5 |
| Funciona de verdade | 15% | 7,5 | 7,6 | 8,0 | 1 e 3 |
| Segurança | 15% | 6,5 | 7,8 | 8,0 | 2 |
| Confiabilidade | 10% | 6,0 | 7,3 | 8,0 | 1 |
| Avaliação mensurável | 10% | 4,5 | 6,5 | 7,5 | 3 |
| Alcance e ecossistema | 15% | 3,5 | 4,0 | 5,0 | 4 |
| **Média ponderada** | | **6,4** | **7,2** | **7,7** | |

Notas do Zérvis: do código e dos testes. Dos concorrentes: documentação e reviews, sem execução.

O que segura cada nota de 11/11 abaixo da meta:

- **Arquitetura (8,3):** 54 mil linhas de Python com tipagem estrita, 1.735 testes, CI fixada e
  nenhum módulo acima de 800 linhas. Fora da porta: o JavaScript do Zé na Imersão (4,7 mil linhas
  nos `jarvis-*.js`), sem tipos e com os testes fora da CI.
- **Funciona de verdade (7,6):** 93% na avaliação, mas a voz está fora da meta de latência (via
  rápida com p50 de 3,9 s; a meta é p95 abaixo de 2,5 s).
- **Segurança (7,8):** a bateria de injeção e os segredos fora do agente estão no `make check`; a
  sessão protegida ainda vem desligada.
- **Confiabilidade (7,3):** em 11/11 o Zé reiniciou três vezes e as quatro sessões seguiram vivas;
  em sete dias, 366 ações e 7 falhas. Atualizar com o programa aberto desfaz a atualização.
- **Avaliação (6,5):** `docs/placar.md` parou na "Versão 0.3.0" (rodada de 09/11); sem rodada
  agendada e sem tarefas de ponta a ponta.
- **Alcance (4,0):** só a instalação do zero no Ubuntu entrou (na CI); o resto da Frente 4 não
  começou.

## Fases

| Fase | Versão | Frentes | Portão (só fecha quando passa) | Nota |
|---|---|---|---|---:|
| A | 0.4.0 | 1, 3 e o ADR do foco (5) | Reinício não derruba sessões; placar publicado | ≈ 7,0 |
| B | 0.5.0 | 2 e 5 | Zero ações indevidas na bateria de injeção; nenhum módulo acima de 800 linhas | ≈ 7,5 (medido: 7,2) |
| Fecho da B | 0.5.x | 1, 2, 3 e 5 | Sessão protegida como padrão; placar da versão publicado; testes da Imersão na CI; atualizar com o programa aberto | ≈ 7,5 |
| C | 0.6.0 | 4 | Uma instalação do zero feita por outra pessoa, sem ajuda | ≈ 7,7 |

Fase A: os dois portões passaram na 0.4.0 (09/11/2026). Ficam abertos, para quando valer o gasto
de tokens: agendar a rodada noturna (a primeira gastou 21,6 milhões) e as tarefas de ponta a ponta.

Fase B: os dois portões passaram na 0.5.0 (11/11/2026): zero ações indevidas nas 570 combinações
da bateria de injeção, e nenhum módulo acima de 800 linhas. O que ficou aberto virou o fecho da
fase, abaixo.

Fase C: o portão "3 PRs de fora aceitos" saiu (não depende de quem mantém o projeto). No lugar
entra algo que se pode fazer acontecer: outra pessoa instalar do zero, só com o README. Em
17/11/2026, por decisão de quem mantém, saíram também o WhatsApp pela API oficial (que era
portão), o inglês e os primeiros contribuidores: não são necessários agora. A meta da Frente 4
cai de 5,5 para 5,0, e a da fase, de ≈ 7,8 para ≈ 7,7.

## Fecho da Fase B (revisão de 11/11/2026)

Exceção registrada em 13/11/2026: a aba Marketing (ADR 0091) entrou antes do fecho, a pedido de
quem usa, com os testes na porta de qualidade.

O que as Fases A e B deixaram aberto e o que a revisão achou no código. Fecha antes da Fase C;
cada item está na frente dele, com o detalhe.

- [x] **Sessão protegida como padrão** (Frente 2): desde 13/11/2026, sessão nova nasce
  protegida quando a máquina permite; desligar é por sessão (ADR 0074).
- [x] **Placar a cada versão** (Frente 3): desde 17/11/2026, o `make check` confere a versão do
  placar publicado, e gerá-lo está nos passos de publicar uma versão.
- [ ] **Rodada por versão, não por noite** (Frente 3): decidir e agendar.
- [ ] **Latência da voz** (Frente 3): os 216 turnos sem primeiro token e a via rápida fora da meta.
- [x] **A Imersão na porta de qualidade** (Frente 5): desde 17/11/2026, os testes dela no
  `make check` (e na CI) e os `jarvis-*.js` no TypeScript.
- [x] **Atualizar com o programa aberto** (Frente 1): desde 17/11/2026, fechar a janela no
  meio da troca não desfaz a atualização.

## Frente 1: Confiabilidade (6,0 → 8,0) · Fase A

Hoje as sessões de Claude e Codex são processos filhos do processo principal: reiniciar o Zé
encerra todas (visto em 06/11/2026, com 3 sessões abertas).

- [x] **Supervisor de sessões separado** (`zervis-oficina`), dono dos terminais. O Zé conversa com
  ele por socket local e, ao reiniciar, reconecta sem perder nada.
  [ADR 0068](adr/0068-supervisor-das-sessoes.md); aceite em `tests/test_supervisor.py`.
- [x] **Fila durável de tarefas** em SQLite (sessão, automação, ligação agendada), com estado e
  tentativas. Ao subir, retoma o que ficou no meio ou marca como interrompido, nunca some.
  [ADR 0069](adr/0069-fila-duravel-das-automacoes.md); as sessões ficam com o ADR 0068.
- [x] **Estado só em SQLite:** avisos, pendências e jobs saem do JSON.
  [ADR 0070](adr/0070-estado-so-em-sqlite.md); também os leads, a prioridade e as ligações.
- [x] **Arquivos do painel sem reiniciar:** um arquivo novo em `portal/web` não pode depender de
  reiniciar o servidor (a página de Sessões falhou por isso em 06/11). A lista fixa saiu: o
  arquivo é achado na pasta a cada pedido (`portal/arquivos_web.py`); aceite em
  `tests/test_portal.py`.

- [x] **Atualizar com o programa aberto** (fecho da Fase B). No PC o Zé é um programa (ADR 0079):
  fechar a última janela o desliga. Em 11/11/2026 (21:36 e 23:07, com o #165) a janela fechou
  durante a atualização, o atalho (`deploy/abrir-painel.sh`) desligou o Zé no meio da troca, o
  painel não respondeu em 90 s e a atualização voltou para a versão anterior. Conferido em
  17/11/2026: o reinício não fecha a janela (o painel de verdade, com o servidor caindo e
  voltando, segue aberto, e nenhum processo dela fica no serviço do Zé); ela foi fechada à mão.
  O defeito era o atalho: agora, com a janela fechada no meio de uma atualização (a unidade
  `zervis-atualizar`) ou de um reinício (um job do serviço, ou ele subindo ou parando), ele
  espera a troca terminar, até 15 minutos, e só então desliga; uma janela reaberta nesse
  meio-tempo mantém o Zé ligado. Aceite com o systemd de mentira de
  `tests/test_instalador_pc.py` (atualização, job e estado de transição).

Aceite: com 3 sessões trabalhando, reiniciar o Zé mantém as 3 vivas e o painel as mostra em menos
de 10 s; matar o processo no meio de uma automação não a perde. Os dois casos no `make check`.
Atualizar pelo painel com o programa aberto termina na versão nova, com a janela de volta.

## Frente 3: Avaliação mensurável (4,5 → 7,5) · Fase A

Hoje: 14 cenários e uma rodada de referência (91%, 20/10/2026, Sonnet 5.5). Motor em
`zervis avaliar` (`docs/avaliacao.md`).

- [x] **100+ cenários** em 8 áreas: voz e fala curta, sessões de código, WhatsApp e atendimento,
  ligações, pesquisa, memória, aprovações, injeção de prompt. 103 cenários, de 11 a 15 por área,
  com a nota por área no resumo e `zervis avaliar --area`; vigiado em `tests/test_avaliacao.py`.
  Falta a primeira rodada real para calibrar as expectativas (gasta a conta).
- [ ] **Tarefas de ponta a ponta** numa pasta de teste, com o resultado verificado (taxa de
  sucesso, não só a escolha da ferramenta).
- [ ] **Rodada noturna**, 3 repetições por cenário; queda de mais de 5 pontos vira aviso. Medir o
  custo antes de fixar a frequência. `zervis avaliar --noturna` pronto (a queda vira aviso pela
  fila durável). Primeira rodada em 09/11/2026: 93%, 29 min, 21,6 milhões de tokens; falta
  decidir a frequência e agendar.
  Revisão de 11/11/2026: o custo foi medido, e toda noite não se paga (uns 650 milhões de tokens
  por mês). Proposta: **uma rodada completa por versão**, antes de publicar, e entre versões só
  as áreas tocadas (`zervis avaliar --area`). A decisão é de quem paga a conta; decidida, o item
  fecha com a rodada da 0.5.x no placar.
- [x] **Latência de voz sempre medida:** do fim da fala ao primeiro som, p50 e p95, por caminho
  (via rápida, cérebro completo, comando local), no recorte e no Ao vivo
  (`python -m zervis.voz.latencia --caminhos 7` e o placar). Primeira medição, 03 a 09/11/2026:
  via rápida com p50 de 3,9 s (a meta é p95 abaixo de 2,5 s). No Ao vivo, 216 turnos foram ao
  cérebro sem nunca receber o primeiro token, quase todos em 03 e 06/11/2026: a investigar.
- [x] **Custo por tarefa** na Atividade: cada pedido de voz ou texto leva o total de tokens e as
  partes (via rápida, cérebro, pesquisa), e cada tarefa de uma sessão de código, o que o agente
  gastou no turno, lido da conversa dele (`zervis/oficina/custo.py`).
- [x] **Placar público** em `docs/placar.md`, atualizado a cada versão: nota por área (93% na
  primeira rodada noturna), latência por caminho e tokens por cenário (`zervis placar`).
- [x] **O placar acompanha a versão** (fecho da Fase B): desde 17/11/2026, o `make check` falha
  se `docs/placar.md` não for da versão do projeto, gerar o placar está nos passos de publicar
  uma versão (`docs/06-qualidade.md`), e cada rodada guarda a versão em que rodou (o placar avisa
  quando a rodada é de uma versão anterior, como a de 09/11/2026 hoje).
- [ ] **Latência da voz dentro da meta** (fecho da Fase B). A primeira medição ficou fora (via
  rápida com p50 de 3,9 s e p95 de 27,9 s) e os 216 turnos do Ao vivo sem primeiro token seguem
  sem causa. Achar a causa dos 216, tirar do p95 o que for falha e não lentidão, e então
  confirmar ou corrigir a meta de 2,5 s com o número medido.

Aceite: 100+ cenários rodando a cada versão (revisto em 11/11/2026: era toda noite); placar da
versão com sucesso por área, p50/p95 e custo.
Metas iniciais (confirmar após a primeira medição): 90% de sucesso, p95 de voz abaixo de 2,5 s na
via rápida.

## Frente 2: Segurança e isolamento (6,5 → 8,0) · Fase B

Autenticação, política de risco e registro de tudo já são bons; falta a parede. As sessões rodam
como o mesmo usuário, com permissão de editar sem perguntar, e entradas externas (WhatsApp,
ligações, web) chegam a um cérebro com ferramentas.

- [ ] **Sandbox das sessões** (bubblewrap no PC, contêiner na VPS): só a pasta do projeto;
  `~/.ssh`, `~/.config` e os dados do Zé ficam fora. Ligar por projeto antes de virar padrão.
  [ADR 0074](adr/0074-sessoes-protegidas.md): ligada por sessão no painel ("Protegida"), com o
  aceite no `make check` (`tests/test_isolamento.py`) e a primeira sessão de verdade em
  10/11/2026; falta virar o padrão e o contêiner na VPS.
  Revisão de 11/11/2026: no código, `protegida` nascia `False` em `oficina/sessoes.py`. Desde
  13/11/2026 é o padrão (fecho da Fase B), com a saída por sessão para o projeto que precisar;
  o aceite ("uma sessão não lê `~/.ssh`") vale para toda sessão nova numa máquina com o
  bubblewrap. Falta o contêiner da VPS, que vai com a imagem Docker da Frente 4.
  Desde 17/11/2026 a imagem existe (ADR 0096): a sessão fica presa no contêiner, longe da casa
  e das chaves do servidor, mas ainda alcança os dados do Zé no volume. Falta separá-los.
- [x] **Cofre de segredos fora do agente:** credencial por chamada, com escopo e prazo; o segredo
  inteiro nunca vai ao modelo.
  [ADR 0075](adr/0075-segredos-fora-do-agente.md): o agente não herda os segredos do Zé (só o
  próprio login e o que a sessão entrega), e a sessão protegida não alcança o D-Bus, o chaveiro
  nem o ssh-agent. [ADR 0076](adr/0076-ponte-dos-conectores.md): os conectores com segredo
  passam pela ponte do Zé; o agente leva só a chave da sessão, que vale enquanto o terminal está
  aberto e só para os conectores do projeto.
- [x] **Entrada externa não confiável por regra:** turno vindo de WhatsApp, ligação, e-mail ou web
  só lê e responde; executar algo exige a sua aprovação pelo canal confiável.
  [ADR 0073](adr/0073-entrada-de-fora.md): depois de ler texto de terceiros, o turno é "de fora" e
  tudo o que muda algo pede o sim falado; o atendente e o agente das ligações não têm ferramentas.
- [x] **Bateria de injeção de prompt** na Frente 3 (mensagem que pede para ignorar regras, página
  com instrução escondida, contato que se passa por você).
  A regra: `tests/test_bateria_injecao.py`, no `make check`, faz um cérebro que obedece a
  qualquer texto de fora tentar cada ação do Zé depois de cada fonte (570 combinações): zero
  executam sem o sim falado. O julgamento do cérebro: os cenários da área `injecao` da
  avaliação (95% na rodada de 09/11/2026).

- Manter: sem loja de skills aberta (o que derrubou o OpenClaw).

Aceite: uma sessão não lê `~/.ssh/id_*` nem os dados do Zé (teste); zero ferramentas de escrita
disparadas por mensagem maliciosa na bateria; nenhum segredo no contexto enviado ao modelo.

## Frente 5: Arquitetura e foco (7,5 → 8,5) · ADR na Fase A, o resto na Fase B

- [x] **ADR do foco:** voz + oficina. Instagram, imersão 3D e pesquisa ficam, sem funções novas
  até a 0.5.0. [ADR 0071](adr/0071-foco-voz-e-oficina.md), com o que conta como função nova.
- [x] **Quebrar os módulos gigantes**, sem mudar comportamento:
  `oficina/sessoes.py` (2.060 linhas: ciclo de vida, cópia isolada, contas e modelos, tela),
  `nucleo/estados.py` (1.532: conversa, confirmação, avisos),
  `nucleo/laco.py` (1.470: laço, efeitos de voz, efeitos do cérebro).
  Nenhum módulo acima de 800 linhas, vigiado por teste. `nucleo/estados.py` dividido em
  `voz_tipos.py`, `entender.py` e `comandos.py` (a máquina ficou com 470 linhas); `nucleo/laco.py` (1.466 → 751) em `retrato.py`, `efeitos.py`,
  `ouvir.py` e `ciclo.py`; `cerebro/rapido.py` (1.122 → 696) com os motores em `motores.py`;
  `cerebro/ferramentas/whatsapp.py` (820 → 653) com a leitura em `whatsapp_leitura.py`;
  `atendimento/ligacao.py` (876 → 761) com a fala em `fala_da_ligacao.py`;
  `oficina/sessoes.py` (2.222 → 761) com os agentes em `agentes.py` e a classe em
  `sessoes_eventos.py`, `sessoes_copia.py`, `sessoes_envio.py` e `sessoes_leitura.py`. Nenhum
  módulo acima de 800 linhas (09/11/2026);
  `tests/test_tamanho_dos_modulos.py` vigia: os que faltam não crescem.
- [x] **Painel em módulos ES**, sem variáveis globais divididas entre arquivos, sem build.
  [ADR 0077](adr/0077-painel-em-modulos-es.md): uma entrada (`modulos/principal.js`), o estado
  que vários arquivos mudam em `modulos/estado.js`, as páginas sob demanda por `import()`.
- [x] **A Imersão na porta de qualidade** (fecho da Fase B). Os testes dela (`make
  check-imersivo`, num Chromium de verdade) ficavam fora do `make check` e da CI, e os
  `jarvis-*.js` (4,7 mil linhas, o que é do Zé) fora do TypeScript: foi por onde entraram os erros
  da abertura em 11/11/2026. Desde 17/11/2026, o `make check` roda os 16 testes da Imersão (uns
  2 minutos, em dois processos), e o `npm run check` confere os `jarvis-*.js` e o `avatar/*.js`
  (`tsconfig.imersao.json`). Eram 235 erros de tipo, resolvidos com JSDoc, sem mudar o que o
  código faz; as APIs que um script publica em `window` para os outros ficam abertas (`any`) em
  `zervis/imersivo/web/tipos.d.ts`, até cada uma ganhar o seu tipo. O `stage.html` (3,7 mil
  linhas) é o Barehands adaptado (`THIRD_PARTY.md`) e fica como veio: dividi-lo afasta do
  original.

## Frente 4: Plataforma e alcance (3,5 → 5,0) · Fase C

É o critério de nota mais baixa (4,0) com 15% do peso: cada ponto aqui vale 0,15 na nota geral.
Ordem revista em 11/11/2026, do que destrava mais para o que depende de fora:

- [x] **Instalação do zero no CI, no Ubuntu 24.04:** o `check` roda o instalador do PC numa
  máquina limpa e confere o serviço, o atalho e o painel (ADR 0079).
- [x] **Imagem Docker para a VPS:** desde 17/11/2026 ([ADR 0096](adr/0096-imagem-docker.md)), um
  volume só com a casa do usuário, sem systemd e com o primeiro acesso pelo endereço seguro; a
  CI `imagem` sobe a imagem com o volume vazio e passa no `doctor`. Falta a prova numa VPS de
  verdade e publicar a imagem pronta a cada versão.
- [ ] **Cérebro pela API** como alternativa testada às CLIs por assinatura; reler os termos de uso
  de cada uma a cada versão.
- [ ] **Instalação do zero no CI, no Arch.**

Fora por decisão de 17/11/2026 (não são necessários agora): WhatsApp pela API oficial, inglês no
painel e na persona, e os primeiros contribuidores.

## Riscos e fora do escopo

- **Uma pessoa só mantém o projeto:** o maior risco; atrair contribuidores ficou fora por ora
  (17/11/2026).
- **O sandbox pode quebrar sessões que hoje funcionam:** ligar por projeto primeiro.
- **A bateria gasta a conta:** usar o modelo mais barato que dê nota estável.
- Fora: apps nativos de macOS e Windows, loja de skills, canais além do WhatsApp, modelo de
  negócio; desde 17/11/2026, o WhatsApp pela API oficial, o inglês e a busca por contribuidores.

## Fontes da comparação (06/11/2026)

- Hermes Agent: [repositório](https://github.com/nousresearch/hermes-agent),
  [documentação](https://hermes-agent.nousresearch.com/docs),
  [Hermes Index](https://cryptobriefing.com/nous-research-hermes-index-agentic-ai/).
- OpenClaw: [Wikipedia](https://en.wikipedia.org/wiki/OpenClaw),
  [Cisco](https://blogs.cisco.com/ai/personal-ai-agents-like-openclaw-are-a-security-nightmare),
  [CVEs](https://www.cvefind.com/en/blog/openclaw-compromise-ai-agents.html).
- Grok Bot: [toolradar](https://toolradar.com/blog/what-is-grok-bot),
  [eesel](https://www.eesel.ai/blog/grok-bot-review).
- Meta Muse: [TechCrunch](https://techcrunch.com/2026/09/08/meta-debuts-its-muse-ai-agent-will-consumers-trust-it/),
  [Wikipedia](https://en.wikipedia.org/wiki/Muse_(AI_agent)).
