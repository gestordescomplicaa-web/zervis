<div align="center">
  <img src=".github/ze-logo.svg" width="168" alt="Logo do Zé, o assistente Zérvis">
  <h1>Zérvis</h1>
  <p><strong>O assistente de voz que trabalha com você: atende o seu WhatsApp, pesquisa empresas,<br>conduz agentes de código e mostra tudo em holograma, no seu Linux.</strong></p>
  <p>Você fala; o Zé faz, pergunta antes do que tem efeito e avisa quando termina.<br>Com o Claude, o Codex ou um modelo que roda no seu próprio computador.</p>
  <p>
    <a href="#um-dia-com-o-zé">Um dia com o Zé</a> ·
    <a href="#o-que-o-zé-faz">O que faz</a> ·
    <a href="#instalar-no-pc">Instalar no PC</a> ·
    <a href="docs/vps.md">Instalar numa VPS</a> ·
    <a href="#arquitetura">Arquitetura</a> ·
    <a href="#o-código-pacote-por-pacote">Código</a> ·
    <a href="docs/roteiro.md">Roteiro</a> ·
    <a href="CONTRIBUTING.md">Contribuir</a>
  </p>
  <p>
    <a href="LICENSE"><img alt="Licença AGPL-3.0-or-later" src="https://img.shields.io/badge/licen%C3%A7a-AGPL--3.0--or--later-45c6d8?style=flat-square"></a>
    <a href="https://github.com/gestordescomplicaa-web/zervis/actions/workflows/check.yml"><img alt="Verificação" src="https://img.shields.io/github/actions/workflow/status/gestordescomplicaa-web/zervis/check.yml?branch=master&label=verifica%C3%A7%C3%A3o&style=flat-square"></a>
    <img alt="Linux" src="https://img.shields.io/badge/plataforma-Linux%20%C2%B7%20Android%20(voz)-45c6d8?style=flat-square">
    <img alt="Python 3.12 a 3.14" src="https://img.shields.io/badge/python-3.12%E2%80%933.14-45c6d8?style=flat-square">
  </p>
</div>

> **Em desenvolvimento ativo, usado todo dia por quem o constrói.** O que está pronto e o que
> está em validação vem marcado em cada função; cada decisão tem o seu registro em
> [docs/adr](docs/adr/).

## Para quem é

Para **gestores e consultores de automação e IA**: quem atende clientes pelo WhatsApp, monta
integrações, fluxos e agentes para empresas, e quer um assistente que faça o trabalho pesado sem
misturar um cliente com outro. Serve também a quem só quer um assistente de voz de trabalho no
próprio Linux, com as mãos livres.

## Um dia com o Zé

Tudo isto é pela voz: no microfone do PC, no navegador ou no celular bloqueado, pelo app Zé Voz.

| Você diz | O Zé faz |
|---|---|
| "Quem me mandou mensagem?" · "O que a Ana falou do orçamento?" | Lê a caixa de entrada e o arquivo do seu WhatsApp, inclusive grupos, e responde curto: quem, quando e o quê. |
| "Responde a Ana: amanhã às 10 eu ligo." | Lê o destinatário e o texto, espera o seu "sim" e envia. Quando ela responder, ele avisa. |
| "Pesquisa a fundo os concorrentes da loja X." | Busca de vários jeitos, lê as melhores páginas e responde com as fontes e as datas. A pesquisa fica guardada. |
| "Qual o CNPJ dela e quem são os sócios?" | Consulta o cadastro da Receita e responde. |
| "Manda um oi para essa empresa no WhatsApp." | Pergunta "é para a Empresa X mesmo, no número tal?" e, com o seu sim, começa a conversa. |
| "Qual post meu teve mais visualização este mês?" | Lê as métricas do seu Instagram, só leitura, e diz qual, quando e por quê provável. |
| "Abre uma sessão no projeto do site e corrige o formulário." | Põe o Claude Code ou o Codex para trabalhar numa cópia isolada, narra o andamento e pede a sua aprovação. |
| "Cria um fluxo no n8n que salva os leads numa planilha." | Monta pelo MCP do n8n do cliente, testa com dados de exemplo e só publica com o seu ok. |
| "Me explica como funciona um RAG." · "Quem é fulano?" | Na Imersão, monta uma cena com gráficos, hologramas 3D, mapas e a foto real, com crédito. |
| "Muda para o local." | Passa a responder por um modelo no seu próprio computador, sem gastar os planos. |
| "Me lembra às 15h de mandar a proposta." | Agenda e avisa na hora, falando. |

## O que o Zé faz

### Voz em todo lugar
| Função | Estado |
|---|---|
| **"Ei Zé"** treinado com a sua voz, conversa contínua, interrupção no meio da fala e fim de turno pela entonação. Voz própria (Piper, primeiro som em cerca de 150 ms) ou da nuvem (ElevenLabs, Fish Audio), com a local de reserva. | Pronto |
| **Três modos**: Silencioso, Normal ("Ei Zé") e Live, uma conversa contínua como uma ligação. | Pronto |
| **No celular**: pelo navegador ou pelo app **Zé Voz** (Android), com a tela bloqueada, pelo fone ou no viva-voz, com o cancelamento de eco do aparelho. Leads do WhatsApp viram notificação com "Ouvir" e "Já vi". | Em validação |

### WhatsApp, como uma recepcionista
| Função | Estado |
|---|---|
| **Caixa de entrada e arquivo**: tudo o que passa pelo seu WhatsApp (conversas e grupos) fica no seu computador, com busca. Ler não gasta token. | Em validação |
| **Leads**: a mensagem de quem quer comprar vira aviso falado, e o Zé lembra a cada 10 minutos, por até uma hora, enquanto você não responde. | Em validação |
| **Responder e começar conversas** pelo que você dita, sempre com o seu "sim". Em grupo ele só lê. | Em validação |
| **Lista de prioridade**: "monitora a Ana" e ele avisa qualquer mensagem dela na hora. Quem ele respondeu por você é vigiado até responder. | Em validação |
| **Atendente automático** à parte, com persona própria, testes antes de publicar e passagem para você. | Em teste |

### Pesquisa e dados de empresas
| Função | Estado |
|---|---|
| **Pesquisa profunda** com buscador próprio (SearXNG, rodando na sua máquina) e leitor de páginas (Trafilatura), atrás de uma trava de rede que só deixa sair para a internet pública. | Em validação |
| **CNPJ** pela BrasilAPI, com o minhareceita.org de reserva: situação, atividade, endereço e sócios. | Em validação |
| **Pesquisas guardadas** na página Pesquisas, com as fontes; "o que achamos sobre X?" responde sem pesquisar de novo. | Em validação |
| **Vigia das fontes**: uma vez por semana testa o buscador, o leitor, o CNPJ, a Wikimedia, o WhatsApp e o Instagram, e avisa o que quebrou. | Em validação |
| **Instagram**, só leitura: perfil e métricas de cada publicação pela API oficial da Meta. | Em validação |

### Oficina de código e integrações
| Função | Estado |
|---|---|
| **Sessões com Claude Code e Codex** num terminal real, por projeto, com as suas contas. Cópia isolada (Git worktree) com prévia, aplicar e descartar. Aprovar pela voz ou pelo painel. | Pronto |
| **Conectores MCP**: cole o JSON ou o `curl` que o serviço fornece. Login OAuth com renovação, permissão por ferramenta, e um cliente nunca aparece no projeto de outro. | Pronto |
| **Integrar qualquer sistema** (skill `integrar-sistema`) e **fluxos no n8n** (skill `fluxos-n8n`): o Zé constrói e testa; o n8n executa; o vigia avisa se um n8n cai. | Pronto |

### Imersão: o Zé em holograma
| Função | Estado |
|---|---|
| **O Zé em 3D** na tela, movido pelas suas mãos pela câmera, com o fundo da câmera ou escuro. | Pronto |
| **Cenas que ele escreve**: "me explica X" vira gráficos, ondas, hologramas 3D montados com peças, modelos 3D livres (inclusive da NASA) e mapas de verdade (IBGE e Natural Earth). | Em validação |
| **Fotos e vídeos reais**, da Wikipédia e do Wikimedia Commons, sempre com crédito, e o print de uma página. | Em validação |
| **Barra de carregamento em holograma**: enquanto pensa, o que o Zé está fazendo, os passos já feitos e quanto cada um costuma levar. | Em validação |

### Cérebros: os seus modelos, inclusive locais
| Função | Estado |
|---|---|
| **Claude** pela assinatura, **Codex** pela conta, ou qualquer rota do **OmniRoute**. Troca pela voz ("muda para o GPT"), com reserva automática entre contas. | Pronto |
| **Respostas rápidas**: um modelo enxuto responde o que é curto, e o resto vai ao cérebro completo. | Pronto |
| **Cérebro local** pelo Ollama (Gemma 4 E4B): as mesmas ferramentas e o mesmo "sim" falado, sem gastar os planos. Medido num Ryzen 5 8500G: acerta a ferramenta certa em 10 de 10 pedidos, com respostas em segundos depois de uma leitura inicial de uns 2 minutos e meio. | Em validação |

### O dia a dia
| Função | Estado |
|---|---|
| **Memória** curta, longa e por projeto, busca no histórico, linha do tempo e nota do dia. **Skills** no padrão aberto agentskills.io, com a sua aprovação. | Pronto |
| **Controle da máquina** no Omarchy: cerca de 370 ações do sistema, cada uma com nível de risco (livre, confirmação falada, frase exata ou proibida). | Pronto |
| **Automações, Foco e avisos**: lembretes, consultas agendadas, frentes de trabalho e uma central que fala só o que importa. | Pronto |
| **Atividade**: tudo o que o Zé executou, inclusive o que foi negado, e quanto cada resposta gastou. | Pronto |
| **Acesso de qualquer lugar** pelo seu domínio, em HTTPS, sem abrir porta, com senha e código do autenticador. | Pronto |
| **Melhora o próprio código**, numa cópia isolada, com testes, a sua aprovação e volta automática se a versão nova não subir. | Pronto |

## Por que é diferente

- **Mãos livres de verdade.** Ler, responder, pesquisar, delegar e aprovar, tudo pela voz, até com
  o celular no bolso. O que tem efeito sempre passa pelo seu "sim", e a frase da pergunta diz
  exatamente o que vai acontecer.
- **O modelo pensa uma vez; o resto roda sem tokens.** Ler o WhatsApp, buscar no arquivo, os
  avisos, o vigia e os fluxos do n8n rodam sem chamar o modelo. E, quando o plano aperta, o
  cérebro local responde de graça.
- **Clientes separados de verdade.** Conectores presos ao projeto pela pasta, sessões
  independentes: o n8n do cliente A nunca entra na sessão do cliente B.
- **Seus dados ficam com você.** Conversas, arquivo do WhatsApp, pesquisas e memória ficam nas
  suas pastas. Segredos em arquivos `0600`, fora da conversa e do repositório.
- **Fontes gratuitas e trocáveis.** Buscador, leitor, CNPJ e imagens vêm de projetos abertos ou
  APIs públicas, cada um atrás de uma interface própria e com um vigia que avisa quando quebram.
- **Falha fechada.** Na dúvida, não envia, não aprova, não apaga, e diz por quê.

## Como se compara

Hermes Agent (Nous Research, MIT) e OpenClaw (MIT) são assistentes generalistas excelentes, com
foco nos mensageiros. O Zérvis escolheu outro foco: **voz, recepção do WhatsApp, pesquisa, oficina
de código e integração de sistemas de clientes, no Linux e na VPS**. Comparação pela documentação
oficial de cada um, em outubro de 2026; detalhes na [matriz comparativa](docs/matriz-comparativa.md).

| | Hermes | OpenClaw | Zérvis |
|---|---|---|---|
| Conversar com o assistente pelos mensageiros | ● Telegram, Discord, Slack, WhatsApp e outros | ● mais de 25 canais | ◐ pela voz e pelo painel; no WhatsApp, o atendente automático em teste |
| Cuidar do seu WhatsApp | — | — | ● caixa, arquivo com busca, leads, responder e iniciar conversas pela voz, com o seu sim |
| Voz no próprio computador | ◐ provedores de voz | ◐ Talk Mode e apps | ● ativação treinada, Live, interrupção, fim de turno e voz local |
| Sessões de código Claude e Codex | — | — | ● terminal real, cópia isolada, aprovação antes de juntar |
| Conectores MCP | ● stdio e HTTP | ● stdio, SSE e HTTP | ● colar JSON ou curl, OAuth, permissão por ferramenta |
| Separação por cliente | ◐ perfis separados | ◐ agentes e gateways isolados | ● conectores por projeto, fora da conversa |
| Skills | ● cria e melhora sozinho | ● ClawHub | ● cria com aprovação |
| Loja aberta de terceiros | ● Skills Hub e plugins | ● ClawHub | — de propósito: nada de código de terceiros dentro do Zé |
| Registro de tudo o que executa | ◐ | ◐ | ● Atividade, inclusive o negado |
| Ações do sistema com nível de risco | ◐ uso do computador | ◐ comandos nos aparelhos | ● Omarchy, com política de risco |
| Configuração | assistente no terminal | `openclaw onboard` | ● toda pela tela |
| Plataformas | Linux, macOS, Windows, Android | Linux, macOS, Windows, iOS, Android | Linux, e o app de voz no Android |

Legenda: **●** tem · **◐** parcial · **—** não tem.

**Quando escolher cada um.** OpenClaw, se o principal é falar com o assistente por muitos
mensageiros e apps de celular. Hermes, se você quer um generalista com centenas de modelos e
integração com IDE. Zérvis, se o seu trabalho é atender, pesquisar, conduzir agentes de código e
ligar sistemas de clientes, falando com ele, com cada cliente no seu lugar.

## Arquitetura

O Zé é **um serviço do seu usuário** (`zervis.service`, systemd) com alguns processos ao lado,
cada um com um papel só. Tudo conversa pelo endereço local (`127.0.0.1`), com token; nada fica
aberto na rede.

### Em números (05/11/2026)

| | |
|---|---|
| **Python** (núcleo, voz, cérebro, domínios) | 47 mil linhas em 231 módulos, 21 pacotes |
| **Go** (WhatsApp nativo, WaCalls) | 20,7 mil linhas |
| **JavaScript** (painel e Imersão, sem etapa de build, com checagem de tipos) | 8,6 mil linhas |
| **Java** (app Zé Voz, Android) | 1,2 mil linhas |
| **Ferramentas do cérebro** | 68, em três servidores MCP do próprio Zé, mais os conectores de cada projeto |
| **Decisões registradas** | 64 ADRs em [docs/adr](docs/adr/) |
| **Testes** | cerca de 1.180, em 149 arquivos, mais o tipo e o lint no `make check` |

### Visão geral

```mermaid
flowchart TB
    subgraph rostos["Rostos: por onde você fala com o Zé"]
        mic["Microfone e caixa do PC<br>PipeWire"]
        nav["Navegador<br>painel + voz por WebSocket"]
        app["App Zé Voz<br>Android, tela bloqueada"]
        holo["Janela da Imersão<br>Chromium + câmera + mãos"]
    end

    subgraph servico["zervis.service (systemd do usuário)"]
        transp["Transportes<br>local · navegador · LiveKit"]
        voz["Voz<br>Ei Zé · VAD · fim de turno · fala"]
        nucleo["Núcleo<br>máquina de estados e laço"]
        cerebro["Cérebro<br>via rápida · Claude · Codex ·<br>OmniRoute · local · reserva"]
        mcp["Ferramentas MCP do Zé<br>jarvis · tempo · foco"]
        portal["Portal :8795<br>painel · API · login"]
        dominios["Domínios<br>oficina · pesquisa · memória · avisos ·<br>automações · foco · sistema · redes"]
    end

    subgraph filhos["Processos filhos (sobem e voltam sozinhos)"]
        imersivo["Servidor da Imersão :8794"]
        searx["SearXNG<br>buscador próprio"]
        aimem["ai-memory<br>memória longa"]
    end

    subgraph atend["zervis-atendimento (processo próprio)"]
        central["Central de Atendimento<br>API local com token"]
        wa["WaCalls (Go)<br>WhatsApp nativo"]
    end

    subgraph fora["Fora do Zé"]
        nuvem["Claude · Codex · Deepgram ·<br>ElevenLabs · Fish Audio"]
        ollama["Ollama :11434<br>Gemma 4 E4B"]
        agentes["Claude Code e Codex<br>sessões num terminal real"]
        clientes["Sistemas dos clientes<br>n8n · CRM · ERP (MCP)"]
        net["Internet pública<br>atrás da trava de rede"]
    end

    mic --> transp
    nav --> transp
    app --> transp
    transp <--> voz <--> nucleo
    nav <--> portal <--> nucleo
    holo <--> imersivo
    nucleo <--> cerebro <--> mcp --> dominios
    cerebro -.-> nuvem
    cerebro -.-> ollama
    dominios --> imersivo
    dominios --> searx --> net
    dominios --> aimem
    dominios --> agentes -- conectores do projeto --> clientes
    nucleo <-->|eventos| central <--> wa
```

### Processos e portas

| Processo | Como roda | Onde escuta | Para quê |
|---|---|---|---|
| **Zé** | `zervis.service`, serviço do usuário; não cai quando o Hyprland reinicia | `127.0.0.1:8795` | núcleo, voz, cérebro, ferramentas e o painel |
| **Imersão** | filho do Zé (`zervis/filho.py`), volta sozinho se cair | `127.0.0.1:8794`, token no cabeçalho | a página do holograma, as cenas e o estado do anel |
| **Central de Atendimento** | `zervis-atendimento`, serviço próprio (ADR 0031) | `127.0.0.1`, porta livre, token `0600` | WhatsApp, caixa, arquivo e atendente automático; reiniciar o Zé não derruba o atendimento |
| **WaCalls** | filho da Central; o Zé compila o Go com a cadeia verificada | `127.0.0.1`, porta livre | a conexão nativa com o WhatsApp (whatsmeow) |
| **SearXNG** | filho do Zé, sobe na primeira busca | `127.0.0.1`, porta livre, segredo novo a cada subida | o buscador da pesquisa profunda |
| **ai-memory** | filho do Zé, binário oficial com SHA-256 conferido | local, HTTP | a memória longa comum ao Claude e ao Codex |
| **Navegador do Zé** | Playwright MCP num Chromium próprio, sem as suas senhas | stdio | ler e usar páginas, com a mesma aprovação falada |
| **LiveKit** | opcional, só local | `127.0.0.1:7880` | a sala de voz do celular, com cancelamento de eco (AEC3) no servidor |
| **Ollama** | serviço da máquina, opcional | `127.0.0.1:11434` | o cérebro local |
| **Acesso de fora** | `cloudflared`, Tailscale ou o domínio da VPS, opcional | HTTPS | painel e voz em outros aparelhos, sem abrir porta no roteador |

### Um pedido por voz, do "Ei Zé" à resposta

```mermaid
sequenceDiagram
    autonumber
    actor V as Você
    participant A as Ativação e VAD<br>(na máquina)
    participant E as Escuta<br>Deepgram nova-3
    participant N as Núcleo
    participant R as Via rápida
    participant C as Cérebro
    participant F as Ferramentas MCP
    participant S as Fala

    V->>A: "Ei Zé" (o chamado nunca sai da máquina)
    A->>N: ATIVO → OUVINDO
    V->>E: o pedido, transcrito enquanto você fala
    E->>N: texto final, com o fim de turno pela entonação
    N->>R: PENSANDO
    alt conversa curta
        R-->>S: responde direto, com a persona enxuta
    else precisa de ferramenta
        R->>C: [completo]
        C->>F: chama a ferramenta (o passo aparece na barra de carregamento)
        opt tem efeito
            F->>V: CONFIRMANDO: "Envio para a Ana: amanhã às 10 eu ligo?"
            V->>F: "sim"
        end
        F-->>C: resultado
        C-->>S: resposta em streaming
    end
    S-->>V: FALANDO, frase a frase (outro "Ei Zé" interrompe)
```

### A máquina de estados

```mermaid
stateDiagram-v2
    [*] --> INATIVO
    INATIVO --> ATIVO: um rosto conectou
    ATIVO --> OUVINDO: "Ei Zé"
    OUVINDO --> PENSANDO: fim da fala
    PENSANDO --> CONFIRMANDO: ação com efeito
    CONFIRMANDO --> PENSANDO: "sim" libera, "não" nega
    PENSANDO --> FALANDO: primeira frase pronta
    FALANDO --> OUVINDO: conversa contínua ou interrupção
    FALANDO --> ATIVO: "ok" ou silêncio
    ATIVO --> INATIVO: o último rosto saiu
```

Regras que viram teste: em INATIVO o microfone fica **fechado**; em FALANDO o que o microfone
ouve não é transcrito (só o chamado, para interromper); CONFIRMANDO só aceita "sim" ou "não", e
silêncio ou 40 s não fazem nada; uma fala por vez, e avisos só saem quando não há pedido em
andamento ([docs/04-arquitetura.md](docs/04-arquitetura.md)).

### O cérebro

| Peça | O que faz |
|---|---|
| **Interface `Brain`** | `start`, `ask`, `interrupt`, `reset`, `close`; devolve texto parcial, chamada de ferramenta, pedido de permissão e fim (`zervis/cerebro/base.py`) |
| **ClaudeBrain** | Claude Agent SDK, sessão contínua, persona `ZE.md`, aprovação falada pelo `can_use_tool` |
| **CodexBrain** | `codex app-server` por JSON-RPC, com as mesmas ferramentas por MCP em stdio |
| **OmniRoute** | o mesmo ClaudeBrain apontado para as rotas do OmniRoute: GPT, Gemini ou automático |
| **LocalBrain** | Ollama, com as mesmas ferramentas e aprovações; só modelos que passaram nos testes do Zé (hoje, o `gemma4:e4b`) ([ADR 0063](docs/adr/0063-cerebro-local.md)) |
| **Via rápida** | a persona enxuta (`RAPIDO.md`) responde o que é curto e devolve `[completo]` quando o pedido precisa do cérebro inteiro |
| **Reserva** | troca de conta ou de provedor antes de qualquer resposta ou ferramenta, sem repetir ações |
| **Baterias e consumo** | quanto resta de cada plano e quanto cada resposta gastou |
| **Revisão** | no fim de uma conversa, um modelo menor propõe memória e skills, que viram pendência para você aprovar |

### As ferramentas

| Servidor MCP | Ferramentas | O que tem |
|---|---|---|
| `jarvis` | 58 | WhatsApp (9) · aprendizado: memória, skills e sugestões (9) · sessões de código (7) · pesquisa profunda, CNPJ e pesquisas guardadas (7) · tela e Imersão (5) · automações (4) · sistema (3) · imagens reais (3) · conectores (3) · modelos 3D (2) · Instagram (2) · navegador, atualizações, manutenção e "sobre o Zé" |
| `tempo` | 3 | linha do tempo, conversas e nota do dia |
| `foco` | 7 | frentes de trabalho e próximos passos |
| `atendente` | 2 | o agente da Central de Atendimento, com persona própria |
| conectores | por projeto | o MCP dos sistemas de cada cliente, preso à pasta do projeto |

O cérebro do Claude roda o servidor dentro do próprio processo e o do Codex, por stdio: nenhuma
das ferramentas do Zé escuta numa porta. Cada chamada cai num destes níveis:

- **Leitura** passa sem perguntar: ler o WhatsApp, pesquisar, listar sessões, ver a tela.
- **Efeito** pergunta em voz alta, com a frase exata do que vai acontecer: enviar, delegar,
  agendar, cadastrar.
- **Sistema** segue a política de risco de cada ação do Omarchy: livre, confirmação falada,
  frase exata ou proibida.
- **Apagar** não existe como ferramenta: excluir é no painel, com você.

### O código, pacote por pacote

| Pacote | Linhas | Responsabilidade |
|---|---:|---|
| `zervis/nucleo` | 7,0 mil | máquina de estados, laço principal, serviços e o autoconhecimento ("o que você sabe fazer?") |
| `zervis/cerebro` | 9,1 mil | a interface `Brain`, Claude, Codex, OmniRoute, local, via rápida, reserva, contas, conectores MCP e OAuth, e as ferramentas (`ferramentas/`) |
| `zervis/voz` | 4,0 mil | o "Ei Zé", a escuta, o Deepgram, o fim de turno, o Live, o filtro de eco do texto e as vozes Piper, ElevenLabs e Fish |
| `zervis/transporte` | 1,1 mil | entrada e saída de áudio trocáveis: PipeWire, navegador (WebSocket) e LiveKit, com o cancelamento de eco |
| `zervis/presenca` | 0,3 mil | os rostos que deixam o Zé ativo: janela no Hyprland, escuta ligada, voz remota |
| `zervis/portal` | 4,6 mil + 4,2 mil web | o painel (17 páginas), a API, a senha com código do autenticador, o pareamento do app e o acesso de fora |
| `zervis/imersivo` | 2,5 mil + 9,3 mil web | a Imersão: servidor, holograma 3D, mãos pela câmera, cenas com 18 tipos de bloco, mapas, fotos e a barra de carregamento |
| `zervis/rosto` | 1,4 mil | o anel, o quadro, o HUD, a janela do Zé e o andamento de cada passo |
| `zervis/oficina` | 4,3 mil | sessões de código (Claude Code e Codex num PTY), cópia isolada, permissões e o modo manutenção |
| `zervis/atendimento` | 3,0 mil + 20,7 mil Go | a Central de Atendimento, o WaCalls e o atendente automático |
| `zervis/pesquisa` | 1,1 mil | buscador (SearXNG), leitor (Trafilatura), CNPJ, pesquisa profunda, pesquisas guardadas e o vigia das fontes |
| `zervis/memoria` | 1,2 mil | memória curta, conversas, histórico, linha do tempo, nota do dia e o ai-memory |
| `zervis/avisos` | 1,6 mil | fila durável, caixa do WhatsApp, leads, lista de prioridade e o que falar quando |
| `zervis/automacoes` | 0,4 mil | lembretes e consultas agendadas |
| `zervis/foco` | 0,7 mil | as frentes de trabalho |
| `zervis/habilidades` | 0,8 mil | skills (agentskills.io), diário de aprendizado e revisão em segundo plano |
| `zervis/sistema` | 0,8 mil | a máquina (Omarchy, outro Linux ou servidor), o catálogo de ações, a política de risco e os vigias do sistema e do n8n |
| `zervis/redes` | 0,5 mil | Instagram, só leitura |
| `zervis/dados` | 0,4 mil | SQLite compartilhado entre processos, com migrações |
| `zervis/avaliacao` | 0,6 mil | a bateria que mede o julgamento do cérebro (`zervis avaliar`) |
| `zervis/persona` | Markdown | quem o Zé é (`ZE.md`) e a persona da via rápida (`RAPIDO.md`) |
| `android/` | 1,2 mil Java | o app Zé Voz |

### Onde mora cada dado

- **SQLite, um banco por área:** atividade, consumo, conversas, sessões, atendimento, arquivo do
  WhatsApp, linha do tempo, vigia do n8n e uso das ferramentas. Migrações automáticas e busca de
  texto.
- **Markdown:** memória curta, skills, persona e a pasta do Zé que a Imersão mostra.
- **JSON com escrita atômica:** avisos, pendências, automações e os sinais da Imersão (estado,
  humor, onda, andamento, comandos da tela).
- **Segredos** em arquivos `0600`, fora do banco, da conversa e do repositório.

### Segurança, camada por camada

- **Só local por padrão.** Cada processo escuta em `127.0.0.1`, com token criado a cada subida.
- **Painel de fora** com senha, código do autenticador (TOTP) e aparelhos lembrados. O app de
  voz recebe só uma chave de voz no pareamento, sem acesso ao painel.
- **Trava de rede** na pesquisa, nas imagens e nas capturas: só sai para endereços públicos da
  internet, nunca para a sua rede local.
- **Atividade**: tudo o que o Zé executou fica registrado, inclusive o que foi negado.
- **O Zé melhora o próprio código** numa cópia isolada, com testes, a sua aprovação e volta
  automática se a versão nova não subir.

### Tecnologias

| Camada | Usa |
|---|---|
| Ativação e VAD | openWakeWord adaptado, no onnxruntime, treinado com a sua voz |
| Fim de turno | Smart Turn v3.2 (Pipecat) |
| Transcrição | Deepgram nova-3, em streaming |
| Voz | Piper com a voz Cadu (local); ElevenLabs e Fish Audio (nuvem) |
| Voz remota | LiveKit (WebRTC) com AEC3; WebSocket pelo navegador |
| Cérebro | Claude Agent SDK, Codex app-server, OmniRoute, Ollama |
| WhatsApp | WaCalls em Go (whatsmeow e pion) |
| Pesquisa | SearXNG, Trafilatura, BrasilAPI e minhareceita.org |
| Imersão | Barehands (base), three.js, MediaPipe Hands, Wikimedia, IBGE e Natural Earth |
| Painel | JavaScript sem etapa de build com tipos checados (tsc), xterm.js |
| Memória longa | ai-memory |
| Navegador | Playwright MCP |
| Acesso de fora | cloudflared, Tailscale |

Créditos e licenças de cada um estão em [THIRD_PARTY.md](THIRD_PARTY.md).

### Princípios

- **Uma linguagem por papel.** Python no núcleo, no cérebro e na voz; Go no WhatsApp; Java no
  app de voz; JavaScript no painel e na Imersão. Só se reescreve noutra linguagem o que uma
  medição apontar como gargalo ([ADR 0032](docs/adr/0032-arquitetura-para-crescer.md)).
- **Fronteiras por processo.** O que precisa ficar de pé sozinho roda à parte, com API local e
  token: a Central de Atendimento, o WaCalls, o buscador e a memória longa.
- **Cérebro trocável.** Claude, Codex, OmniRoute ou um modelo local atrás de uma interface só,
  com as mesmas ferramentas e a mesma aprovação.
- **Os agentes fazem; o Zé conduz.** As sessões são o Claude Code e o Codex de verdade, com as
  skills e os conectores do projeto ([ADR 0037](docs/adr/0037-integracao-com-sistemas.md)).
- **O n8n executa; o Zé constrói e vigia** ([ADR 0038](docs/adr/0038-fluxos-no-n8n-ze-constroi-e-vigia.md)).
- **Cada habilidade é nativa:** um grupo de ferramentas, o autoconhecimento do Zé e uma decisão
  registrada.
- **Uma essência que não muda.** O que o Zé é e não deixa de ser está em
  [docs/essencia.md](docs/essencia.md): nenhuma mudança, nem a feita por ele mesmo, pode
  contrariá-la.

## Instalar no PC

No terminal da sessão gráfica, como usuário comum, com Git, Make e curl instalados:

```sh
git clone https://github.com/gestordescomplicaa-web/zervis.git
cd zervis && deploy/instalar-pc.sh
```

O instalador prepara Python e dependências, os modelos de voz, os agentes de código e o Go
verificado para o WhatsApp. Instala o serviço do usuário, o atalho Zérvis no menu e o comando
`zervis`, e abre o painel na configuração inicial (`http://127.0.0.1:8795/`, só no próprio PC;
acesso por outros aparelhos se liga depois, no painel).

No Ubuntu 24.04, os pré-requisitos são `sudo apt install git make curl xdg-utils pulseaudio-utils`.
Sem as ferramentas de áudio, o instalador avisa; o painel e a conversa por texto continuam
funcionando. O controle completo da máquina é no Omarchy; outros Linux têm o controle reduzido.

## Instalar numa VPS

Num Ubuntu 24.04 ou parecido, com um usuário comum (não root) e Git, Make e curl instalados:

```sh
git clone https://github.com/gestordescomplicaa-web/zervis.git
cd zervis && deploy/instalar-servidor.sh
```

O instalador prepara tudo, deixa o Zé rodando como serviço e termina com um endereço HTTPS e um
código de primeiro acesso: abra o endereço, crie a senha e ligue o código do autenticador, sem
túnel SSH. O passo a passo e o login do Claude e do Codex estão em [docs/vps.md](docs/vps.md).

## O comando `zervis`

| Comando | O que faz |
|---|---|
| `zervis status` | Se o serviço está de pé, a versão e o endereço do painel |
| `zervis doctor` | Cada função, "Disponível" ou "Indisponível", com o motivo e como resolver |
| `zervis update` | Atualiza para a versão publicada mais nova e reinicia; se o painel não voltar, volta para a anterior (`--desenvolvimento` segue a `master`) |
| `zervis logs` | O registro do serviço, ao vivo |
| `zervis abrir` | Abre o painel no navegador |
| `zervis avaliar` | A bateria de avaliação do cérebro: o julgamento do Zé medido em cenários ([como funciona](docs/avaliacao.md)) |
| `zervis uninstall` | Remove o serviço, o atalho e o comando; os seus dados ficam, a não ser que você peça |

Sem terminal, o mesmo `update` fica em **Ajustes → Atualizações**, no painel: o Zé procura uma vez
por dia, avisa quando há versão nova, mostra o que muda e atualiza num clique.

## Desenvolver

Linux, Python 3.12 a 3.14, Node.js 22+ e [uv](https://docs.astral.sh/uv/):

```sh
uv sync
npm ci
make check                 # formatação, lint, tipos e testes
uv run python -m zervis    # sobe o Zé; o painel abre em http://127.0.0.1:8795/
```

Na primeira subida, o Zé baixa os modelos de som e a voz (Cadu, 63 MB), confere o SHA-256 de cada
um e abre a configuração inicial: perfil, acesso ao Claude (assinatura ou chave de API) e a chave
do Deepgram para a voz. Sem a palavra de ativação treinada, ele atende pelo painel e pelo
teclado. `make instalar` instala o serviço do systemd do usuário e o atalho "Zérvis" no menu de
aplicativos (`PORTA=8796 make instalar` para outra porta).

Numa VPS, sem tela e sem som, o Zé não oferece o que a máquina não tem.

## Onde ficam os seus dados

| Raiz | Padrão | O que tem |
|---|---|---|
| Configuração | `~/.config/zervis` | `config.toml`, `perfil.json` (quem é você), chaves (`0600`), conectores MCP |
| Dados | `~/.local/share/zervis` | memória, skills, conversas, linha do tempo, Foco, sessões, automações |
| Estado | `~/.local/state/zervis` | o momento: status, tempos, consumo, avisos |

Nada é enviado ao repositório nem a terceiros sem pedido explícito. Nenhum nome, fuso ou caminho de
alguém fica fixo no código: o que é seu vem da configuração. `ZERVIS_PERFIL=<nome>` usa outro
conjunto de pastas (`zervis-<nome>`); `ZERVIS_RAIZ=<pasta>` põe as três dentro de uma pasta só.

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/roteiro.md](docs/roteiro.md) | Para onde o projeto vai, em ordem |
| [docs/pc.md](docs/pc.md) | O Zé no PC: instalação, verificação e limites |
| [docs/vps.md](docs/vps.md) | O Zé numa VPS: instalação, acesso e celular |
| [android/README.md](android/README.md) | O app de voz Zé Voz: instalar, parear e como funciona |
| [docs/avaliacao.md](docs/avaliacao.md) | A bateria que mede o julgamento do cérebro |
| [docs/essencia.md](docs/essencia.md) | O que o Zé é e não deixa de ser |
| [docs/imersivo/PERSONALIZAR.md](docs/imersivo/PERSONALIZAR.md) | Como a Imersão funciona e o que dá para personalizar (JSON) |
| [docs/conceitos.md](docs/conceitos.md) | Conversa, voz, foco, sessão, automação, memória e skill |
| [docs/04-arquitetura.md](docs/04-arquitetura.md) | Componentes, estado, fluxos e contratos |
| [docs/matriz-comparativa.md](docs/matriz-comparativa.md) | Hermes, OpenClaw e Zérvis, função por função |
| [docs/06-qualidade.md](docs/06-qualidade.md) | Regras de engenharia (obrigatórias) |
| [docs/07-sistema-omarchy.md](docs/07-sistema-omarchy.md) | O Omarchy no núcleo: ações, eventos e risco |
| [docs/adr/](docs/adr/) | Decisões de arquitetura |
| [THIRD_PARTY.md](THIRD_PARTY.md) | Código e modelos de terceiros |

## Licença

[AGPL-3.0-or-later](LICENSE). A voz usa o [Piper](https://github.com/OHF-Voice/piper1-gpl)
(GPL-3.0) e a voz Cadu (CC0); os demais componentes de terceiros e as licenças estão em
[THIRD_PARTY.md](THIRD_PARTY.md).
