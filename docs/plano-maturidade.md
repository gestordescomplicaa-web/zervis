# Plano de maturidade

Data: 06/11/2026. Nasceu de uma análise de CTO que comparou o Zérvis com Hermes Agent, OpenClaw,
Grok Bot e Meta Muse. Nota atual **6,4/10 como produto**; meta **7,8**, sem perder o que o Zérvis
já faz melhor que todos: voz e condução de sessões de código.

Regra durante as Fases A e B: **funções novas congeladas**. Entram correções e o que as frentes
pedem. Cada item feito é marcado aqui no mesmo PR que o entrega.

## Placar

| Critério | Peso | Hoje | Meta | Frente |
|---|---:|---:|---:|---|
| Arquitetura e engenharia | 20% | 7,5 | 8,5 | 5 |
| Proposta e diferencial | 15% | 8,0 | 8,5 | 5 |
| Funciona de verdade | 15% | 7,5 | 8,0 | 1 e 3 |
| Segurança | 15% | 6,5 | 8,0 | 2 |
| Confiabilidade | 10% | 6,0 | 8,0 | 1 |
| Avaliação mensurável | 10% | 4,5 | 7,5 | 3 |
| Alcance e ecossistema | 15% | 3,5 | 5,5 | 4 |
| **Média ponderada** | | **6,4** | **7,8** | |

Notas do Zérvis: do código e dos testes. Dos concorrentes: documentação e reviews, sem execução.

## Fases

| Fase | Versão | Frentes | Portão (só fecha quando passa) | Nota |
|---|---|---|---|---:|
| A | 0.4.0 | 1, 3 e o ADR do foco (5) | Reinício não derruba sessões; placar publicado | ≈ 7,0 |
| B | 0.5.0 | 2 e 5 | Zero ações indevidas na bateria de injeção; nenhum módulo acima de 800 linhas | ≈ 7,5 |
| C | 0.6.0 | 4 | Atendimento pela API oficial do WhatsApp; 3 PRs de fora aceitos | ≈ 7,8 |

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

Aceite: com 3 sessões trabalhando, reiniciar o Zé mantém as 3 vivas e o painel as mostra em menos
de 10 s; matar o processo no meio de uma automação não a perde. Os dois casos no `make check`.

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
- [x] **Latência de voz sempre medida:** do fim da fala ao primeiro som, p50 e p95, por caminho
  (via rápida, cérebro completo, comando local), no recorte e no Ao vivo
  (`python -m zervis.voz.latencia --caminhos 7` e o placar). Primeira medição, 03 a 09/11/2026:
  via rápida com p50 de 3,9 s (a meta é p95 abaixo de 2,5 s). No Ao vivo, 216 turnos foram ao
  cérebro sem nunca receber o primeiro token, quase todos em 03 e 06/11/2026: a investigar.
- [ ] **Custo por tarefa** na Atividade. Cada pedido de voz ou texto já leva o total de tokens e
  as partes (via rápida, cérebro, pesquisa); falta o das tarefas das sessões de código.
- [x] **Placar público** em `docs/placar.md`, atualizado a cada versão: nota por área (93% na
  primeira rodada noturna), latência por caminho e tokens por cenário (`zervis placar`).

Aceite: 100+ cenários rodando toda noite; placar na 0.4.0 com sucesso por área, p50/p95 e custo.
Metas iniciais (confirmar após a primeira medição): 90% de sucesso, p95 de voz abaixo de 2,5 s na
via rápida.

## Frente 2: Segurança e isolamento (6,5 → 8,0) · Fase B

Autenticação, política de risco e registro de tudo já são bons; falta a parede. As sessões rodam
como o mesmo usuário, com permissão de editar sem perguntar, e entradas externas (WhatsApp,
ligações, web) chegam a um cérebro com ferramentas.

- [ ] **Sandbox das sessões** (bubblewrap no PC, contêiner na VPS): só a pasta do projeto;
  `~/.ssh`, `~/.config` e os dados do Zé ficam fora. Ligar por projeto antes de virar padrão.
- [ ] **Cofre de segredos fora do agente:** credencial por chamada, com escopo e prazo; o segredo
  inteiro nunca vai ao modelo.
- [ ] **Entrada externa não confiável por regra:** turno vindo de WhatsApp, ligação, e-mail ou web
  só lê e responde; executar algo exige a sua aprovação pelo canal confiável.
- [ ] **Bateria de injeção de prompt** na Frente 3 (mensagem que pede para ignorar regras, página
  com instrução escondida, contato que se passa por você).
- Manter: sem loja de skills aberta (o que derrubou o OpenClaw).

Aceite: uma sessão não lê `~/.ssh/id_*` nem os dados do Zé (teste); zero ferramentas de escrita
disparadas por mensagem maliciosa na bateria; nenhum segredo no contexto enviado ao modelo.

## Frente 5: Arquitetura e foco (7,5 → 8,5) · ADR na Fase A, o resto na Fase B

- [x] **ADR do foco:** voz + oficina. Instagram, imersão 3D e pesquisa ficam, sem funções novas
  até a 0.5.0. [ADR 0071](adr/0071-foco-voz-e-oficina.md), com o que conta como função nova.
- [ ] **Quebrar os módulos gigantes**, sem mudar comportamento:
  `oficina/sessoes.py` (2.060 linhas: ciclo de vida, cópia isolada, contas e modelos, tela),
  `nucleo/estados.py` (1.532: conversa, confirmação, avisos),
  `nucleo/laco.py` (1.470: laço, efeitos de voz, efeitos do cérebro).
  Nenhum módulo acima de 800 linhas, vigiado por teste. `nucleo/estados.py` dividido em
  `voz_tipos.py`, `entender.py` e `comandos.py` (a máquina ficou com 470 linhas);
  `tests/test_tamanho_dos_modulos.py` vigia: os que faltam não crescem.
- [ ] **Painel em módulos ES**, sem variáveis globais divididas entre arquivos, sem build.

## Frente 4: Plataforma e alcance (3,5 → 5,5) · Fase C

- [ ] **WhatsApp pela API oficial** (Cloud API) para o atendimento a clientes; o caminho atual
  (whatsmeow e o protocolo de ligação) fica como opção pessoal. Banimento é fatal num atendimento.
- [ ] **Cérebro pela API** como alternativa testada às CLIs por assinatura; reler os termos de uso
  de cada uma a cada versão.
- [ ] **Instalação do zero no CI** (Ubuntu 24.04 e Arch); imagem Docker para a VPS.
- [ ] **Inglês** no painel e na persona, português como padrão.
- [ ] **Primeiros contribuidores:** issues para iniciantes, placar como vitrine, vídeo da voz e da
  oficina.

## Riscos e fora do escopo

- **Uma pessoa só mantém o projeto:** o maior risco; a Frente 4 começa a atacá-lo.
- **O sandbox pode quebrar sessões que hoje funcionam:** ligar por projeto primeiro.
- **A bateria gasta a conta:** usar o modelo mais barato que dê nota estável.
- Fora: apps nativos de macOS e Windows, loja de skills, canais além do WhatsApp, modelo de
  negócio.

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
