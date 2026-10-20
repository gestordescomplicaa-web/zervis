# 04 — Arquitetura

Data: 06/10/2026, revisada em 10/10/2026 (ADR 0014 e 0015: o imersivo dentro do Zé, três camadas de
modelos e as sessões de código próprias no lugar do Orca). Detalhes seguem o
[roteiro.md](roteiro.md).

Implementação em 12/10/2026: as personas são recursos em `jarvis/persona/`; consulta e publicação
do ai-memory usam o mesmo binário e raiz de dados. O imersivo valida Host/Origin e exige token
por instância nos pedidos e nas leituras de estado (ADR 0019). Sessões isoladas com trabalho
pendente não podem ser excluídas. Registros operacionais ainda estão em JSON/JSONL; o SQLite
descrito abaixo é uma migração planejada, não implementada. Codex funciona nas sessões de código;
no cérebro, permanece planejado.

> **Atualizado em parte.** Este documento descreve a arquitetura até 10/10/2026: o rosto e as mãos
> ainda aparecem como o Barehands, que depois entrou no Zé como o modo imersivo (ADR 0014). O
> quadro atual está no [README](../README.md#arquitetura) e nos ADRs 0032 a 0038.

## Visão geral

```
                     ┌──────────────────────── Barehands (rosto + mãos) ───────────────────────┐
                     │  anel (state/state, mood.json, wave.json)   quadro (POST /cmd, cards)   │
                     └──────────────▲───────────────────────────────────────▲──────────────────┘
                                    │ sinais em arquivo                     │ cards / diff / pendências
┌───────────────────────────────────┴───────────────────────────────────────┴───────────────────┐
│                                   Zérvis   (um processo, systemd --user)                      │
│                                                                                               │
│   Interruptor ──► Máquina de estados ◄── Voz: ativação ─ escuta ─ transcrição ─ saída (Cadu)  │
│   Sistema (Omarchy/Hyprland: eventos e ações) ──► avisos e ferramentas                        │
│   (front aberto?)        │                                                                    │
│                          ├──► Cérebro (interface única) ──► ClaudeBrain (Agent SDK)           │
│                          │                              └─► CodexBrain  (SDK/app-server)      │
│                          │            ▲ ferramentas via MCP                                    │
│                          │   ┌────────┴──────────────────────────────────────────────┐        │
│                          │   │ servidor MCP "jarvis": memória · histórico · skills ·  │        │
│                          │   │ automações · avisos · sessões de código · sistema      │        │
│                          │   └───────────────────────────────────────────────────────┘        │
│                          ├──► Avisos (fila durável)  ◄── Automações (agendador)               │
│                          │                           ◄── Sessões de código (Claude, Codex)     │
│                          └──► Revisão em segundo plano ──► Pendências (memória/skills)        │
│                                                                                               │
│   Estado: ~/.local/state/zervis/jarvis.db (SQLite WAL) + ~/.local/share/zervis/ (Markdown)    │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Componentes

| Pacote | Responsabilidade | Não faz |
|---|---|---|
| `jarvis/nucleo` | Máquina de estados, laço principal, lock de instância única, desligamento limpo | Lógica de domínio |
| `jarvis/presenca` | Decide ATIVO/INATIVO e **qual rosto** está conectado (mesa = Barehands, remoto = celular) | Ligar a janela |
| `jarvis/transporte` | Entrada e saída de áudio trocáveis: `TransporteLocal` (PipeWire) e `TransporteLiveKit` (sala WebRTC local, celular via Tailscale) | Transcrever ou sintetizar |
| `jarvis/voz` | Ativação "Ei Zé", captura, transcrição, normalizador de fala, saída Cadu com streaming | Decidir o que dizer |
| `jarvis/rosto` | Anel (estado, cor, onda), painel de cérebros (ADR 0010) e quadro (cards, pendências) | — |
| `jarvis/cerebro` | Interface `Brain` e implementações Claude/Codex; persona; sessão contínua; catálogo e baterias (ADR 0010) | Guardar estado próprio |
| `jarvis/ferramentas` | Servidor MCP com as ferramentas do Zé para o cérebro | Falar com o usuário |
| `jarvis/memoria` | `USUARIO.md` e `JARVIS.md` curtos com limite, varredura, histórico (ai-memory) | — |
| `jarvis/skills` | Catálogo progressivo, escrita com pendência e diff, uso e curadoria | — |
| `jarvis/automacoes` | Jobs (`jobs.json` atômico), agendador | Falar diretamente: entrega para os avisos |
| `jarvis/avisos` | Fila durável com prioridade, expiração e retenção enquanto inativo | — |
| `jarvis/oficina` | Sessões de código próprias (agentes Claude/Codex por pasta de projeto, com conversa que continua), explorador de arquivos e o modo manutenção | Codar ele mesmo |
| `jarvis/imersivo` | O modo imersivo (ADR 0014): servidor, página, avatar, mãos | — |
| `jarvis/sistema` | Omarchy e Hyprland: catálogo de ações dos metadados `omarchy-*`, leitura de estado, eventos (hooks e socket do Hyprland), política de risco | Simular teclado |
| `jarvis/revisao` | Revisão em segundo plano a cada N turnos → pendências | Aplicar mudanças sem aprovação |

## Máquina de estados do núcleo

```
INATIVO ──(front abriu)──► ATIVO ──("Ei Zé")─────► OUVINDO ──(fim da fala)──► PENSANDO
   ▲                          ▲                                                   │
   │(front fechou: de          │◄──────────────(fala terminou)─── FALANDO ◄───────┘
   │ qualquer estado,          │                                     │("Ei Zé" = interromper)
   │ corta fala e microfone)   │◄──("sim"/"não"/tempo)── CONFIRMANDO ◄┘(pedido de aprovação)
```

Regras invariantes (cada uma vira teste):
1. Em INATIVO o microfone está **fechado** e nenhuma saída de voz ou card é emitida.
2. Só se entra em OUVINDO pela palavra de ativação ou pela continuação da conversa que ela abriu;
   um pedido consome uma autorização e só a resposta a ele concede a próxima. "ok", 8 s de
   silêncio ou fechar a janela encerram a conversa ([ADR 0009](adr/0009-conversa-continua-com-ok.md)).
3. Em FALANDO o microfone não é transcrito (proteção de eco), exceto pelo detector de ativação
   para interromper.
4. CONFIRMANDO só aceita "sim"/"não"; qualquer outra coisa, silêncio ou mais de 40 s ⇒ nada acontece.
5. Uma fala por vez. Avisos só saem em ATIVO e sem pedido em andamento.

## Presença (liga/desliga e rosto ativo)

O Zé está ATIVO quando há pelo menos um rosto conectado. Rostos:
- **Mesa:** janela do Barehands aberta → `TransporteLocal` (microfone MIC FX e saída do PC).
- **Remoto:** app do celular conectado à sala do LiveKit → `TransporteLiveKit` (microfone e fone do celular).
  Nesse modo o microfone e a saída do PC ficam desligados.
- Os dois ao mesmo tempo: vale o último que conectou (regra a confirmar no uso).

### Sinal da janela (modo mesa)

- Fonte primária (Prova 3): socket de eventos do Hyprland, `openwindow`/`closewindow` da classe
  `chrome-127.0.0.1__stage.html-Default`; chega ~0,2 s antes das consultas e não custa nada parado.
- Conferência: `hyprctl clients -j` ao iniciar, ao reconectar o socket (o Hyprland pode reiniciar)
  e a cada 5 s. Socket caído e consulta falhando ⇒ INATIVO.
- Janela em outra área de trabalho conta como aberta. `barehands-window.service` fica só como
  informação: não enxerga janela aberta fora do serviço.
- Transição para INATIVO: corta a fala em andamento, fecha a captura, anel em "inativo".
- Transição para ATIVO: anel em "ocioso"; se houver pendências, **um** resumo falado.

## Celular (modo remoto) — última fase do roadmap

```
celular (PWA: botão, anel, avisos) ──WebRTC──► livekit-server (no PC, só local)
        ▲            via Tailscale                    │
        └──────── voz do Cadu ◄──── Zé (participante da sala pelo SDK Python rtc)
```
- O serviço do Zé emite tokens de sala de curta duração; o PWA pede um token a um endpoint do
  `Zé` publicado só na rede do Tailscale (`tailscale serve`, HTTPS).
- O áudio recebido entra no mesmo pipeline do modo mesa (detector → transcrição → cérebro);
  a voz sintetizada sai pela faixa publicada na sala.
- O PWA mostra o mesmo estado do anel e os avisos/pendências, e permite aprovar tocando,
  sempre com confirmação.
- Detalhes e riscos: [ADR 0005](adr/0005-celular-por-livekit-e-tailscale.md).

## Cérebro

O cérebro é o **cérebro base**: rápido, conversa, decide e delega. Ele **não coda**; codificar e
avaliar projetos é dos agentes do Orca ([ADR 0007](adr/0007-cerebro-base-rapido-e-codificacao-no-orca.md)).

Interface única (assíncrona):

```python
class Brain(Protocol):
    async def start(self, persona: str, mcp_servers: dict) -> None
    async def ask(self, text: str) -> AsyncIterator[Event]   # Texto parcial, Ferramenta, Pedido de permissão, Fim
    async def interrupt(self) -> None
    async def reset(self) -> None                            # nova sessão (a memória recarrega)
    async def close(self) -> None
```

- **ClaudeBrain:** `claude-agent-sdk` (`ClaudeSDKClient`), sessão contínua, `include_partial_messages`
  para falar por frase, `can_use_tool` para a aprovação falada, persona como acréscimo ao prompt
  `claude_code`, skills do Zé visíveis, servidor MCP `jarvis` registrado.
- **ClaudeBrain via OmniRoute:** o mesmo `ClaudeBrain` com o CLI apontado para o OmniRoute local
  (`ANTHROPIC_BASE_URL`), usando as rotas dele como modelo ([ADR 0008](adr/0008-omniroute-como-provedor-do-cerebro.md)).
- **CodexBrain:** pelo `codex app-server` (JSON-RPC por stdio), com MCP por stdio e aprovação
  respondida pelo Zé; confirmado na Prova 2 ([ADR 0002](adr/0002-cerebro-por-sdk-de-agente.md)).
- **Toda sessão** passa `permission_mode="default"` explícito: na Prova 4 a aprovação foi pulada
  sem isso.
- **Autenticação:** login de assinatura do CLI instalado (Claude Code / Codex), que é como o
  o usuário usa hoje. Chave de API fica como opção futura. O Zé **não** implementa OAuth próprio.
- O núcleo é síncrono com threads (herança do atual); o cérebro roda num **laço asyncio próprio**
  em uma thread dedicada, conversando com o núcleo por filas. Assim o laço do microfone nunca
  espera rede.

## Ferramentas do cérebro (servidor MCP "jarvis")

| Ferramenta | Ações | Observação |
|---|---|---|
| `memoria` | `add`, `replace`, `remove` (alvo `usuario` ou `jarvis`) | Escritas vão para pendência (R4.3) |
| `historico` | `buscar(termos, projeto?)`, `ler(pagina)` | ai-memory, via `lembrar.py` |
| `skills` | `listar`, `ver(nome, arquivo?)`, `propor(criar|patch|apagar)` | Propostas viram pendência com diff |
| `automacoes` | `criar`, `listar`, `pausar`, `retomar`, `rodar`, `remover` | Bloqueado dentro de execução de automação |
| `oficina` | `sessoes`, `delegar(tarefa, projeto, agente)`, `responder(pergunta)`, `mandar_texto(sessao)` | Usa a orquestração nativa do Orca |
| `sistema` | `estado(area)`, `acoes(busca)`, `executar(acao, args)` | Nível de risco aplicado antes de executar ([07](07-sistema-omarchy.md)) |
| `avisos` | `pendentes`, `silenciar`, `religar` | — |

Expor como MCP resolve o agnosticismo: Claude e Codex consomem o mesmo servidor. É tudo local:
no Claude o servidor roda **dentro do processo** (sem porta); no Codex, como subprocesso por
**stdio** (sem porta). Nada fica escutando em `localhost`. Detalhes no [ADR 0002](adr/0002-cerebro-por-sdk-de-agente.md).

## Dados e arquivos

| Caminho | Conteúdo | Formato |
|---|---|---|
| `~/.config/zervis/config.toml` | Configuração (provedor, limites, vozes, horários) | TOML validado por esquema, com versão |
| `~/.local/share/zervis/memoria/USUARIO.md`, `JARVIS.md` | Memória curta | Markdown, entradas separadas por `§` |
| `~/.local/share/zervis/skills/<nome>/SKILL.md` | Skills aprovadas | agentskills.io |
| `~/.local/share/zervis/skills/.arquivo/` | Skills arquivadas pela curadoria (sem uso há 30 dias) | — |
| `~/.local/share/zervis/diario.jsonl` | Diário de aprendizado: sugestão aprovada/descartada, memória e skill gravadas, skill arquivada | JSON por linha, só cresce |
| `~/.local/share/zervis/pasta/*.md` | A pasta do Zé (bolha "Zé" do Barehands): quem sou e conexões, memória, skills, automações, aprendizado, consumo | Markdown gerado a cada 15 s, só a nota que mudou |
| `~/.local/state/zervis/consumo.json`, `consumo-dias.json` | Tokens do dia (e pedidos resolvidos sem o cérebro) e dos últimos 60 dias | JSON |
| `~/.local/state/zervis/uso-ferramentas.json` | Usos e último uso de cada ferramenta do cérebro | JSON |
| `<imersivo>/state/{decisao,eficiencia,mapa,mapa-abrir}.json` | O cérebro na tela: card de decisão, medidor, mapa do cérebro navegável por grupo e conexão | JSON com `ts`; velho (90 s) some da tela |
| `<imersivo>/state/maos-pedido.json` | Pedido por voz ao Barehands: calibrar as mãos, voltar ao padrão, brilho da câmera e tema de cores | JSON com `pedido` e `acao` |
| `<imersivo>/state/tela-{comando,estado}.json` | O Zé na própria tela (`tela_agir` / `tela_ver`): ações em ordem e o estado de volta | JSON com `id`; comando com mais de 30 s não roda |
| `<imersivo>/state/teclado{,-resposta}.json` | O Teclado do Núcleo: pedido escrito (POST /teclado) e a resposta conforme é falada | JSON com `id`/`pedido`; pedido com mais de 30 s não roda |
| `<imersivo>/barehands.json` | O manifesto do Núcleo: os orbes (id, título, tipo, apelidos falados, descrição); a página, a voz e a persona leem dele | JSON `orbs`; sem ele, os orbes do padrão |
| `~/.local/state/zervis/manutencao/` | Modo manutenção: `estado.json` (ligado, agente, pedidos), `resposta-<id>.md` e `pergunta-<id>.md` gravados pelo agente, `reinicio.json` do reinício seguro | Aperto de mão por arquivo com a sessão de código |
| `~/.local/state/zervis/evidencias.jsonl` | Evidências do uso real para a rodada de melhoria | Uma linha JSON por evento; 30 dias |
| `~/.local/state/zervis/jarvis.db` | Avisos, pendências, uso de skills, execuções de jobs, eventos | SQLite (WAL), migrações numeradas |
| `~/.local/share/zervis/automacoes/jobs.json` | Jobs | JSON com escrita atômica |
| `~/.local/state/zervis/status.json` | Batimento e estado para diagnóstico | JSON, 1 Hz |
| `<imersivo>/state/*` | Sinais do anel | Contrato do Barehands |

Segredos: nunca nesses arquivos. Variável de ambiente do serviço ou chaveiro (`secret-tool`).

## Fluxos principais

**Pedido por voz:** ATIVO → ativação → OUVINDO → transcrição → (comando de console? executa
local) → PENSANDO → `Brain.ask` → frases parciais passam por `fala.py` → FALANDO frase a frase →
fim → ATIVO. A revisão em segundo plano conta o turno.

**Aprovação de ferramenta do próprio Zé:** o SDK chama `can_use_tool` → descrição falada →
CONFIRMANDO → "sim" libera, "não" nega com o motivo dito. Ações só de leitura dentro das pastas do
Zé passam sem perguntar.

**Delegação ao Orca:** cérebro chama `oficina.delegar` → `orca orchestration worker-start` → núcleo
espia a caixa do Run (`check --peek`) → `worker_done` vira aviso "deu certo/falhou" → falado se ATIVO.

**Automação:** agendador vê job vencido → valida → roda (script ou cérebro numa sessão separada) →
resultado vira aviso → falado se ATIVO; senão fica pendente para o resumo ao reativar.

**Aprendizado:** a cada N turnos → revisão (sessão separada do cérebro, prompts do Hermes
adaptados) → propostas de memória/skill → pendências com diff → card no quadro → "Ei Zé, aprovar
a skill" → aplicada.

## Ambiente de execução

- Python 3.12+, ambiente próprio gerenciado por `uv` (fim da dependência do venv do Hermes).
- Dependências fixadas por versão exata (lição do Hermes contra ataques de cadeia de suprimentos).
- `zervis.service` (systemd --user), `Restart=on-failure`, sem `PartOf=graphical-session.target`
  para não morrer quando o Hyprland reinicia (lição de 06/10/2026), mas esperando a sessão de áudio.
- Go fica como candidato para um núcleo binário único quando a arquitetura estabilizar.


### Brain / Work / Focus no Barehands (07/10/2026)

A pasta mantém mapa, decisões e histórico. A thread da pasta também consulta
a oficina em modo somente leitura e escreve rotina.json: projetos, agentes e tarefas
delegadas. A consulta tem timeout, não roda no laço de áudio e não exporta prompts,
mensagens nem comandos. Uma falha informa indisponibilidade, sem conservar agentes
com estado falsamente atual. O identificador da frente é worktreeId, não seu caminho.

O núcleo publica presenca.json junto do status a cada segundo. O front usa o batimento
para exibir o estado de voz com validade curta. Brain desenha relações, Work lista
objetos, Focus expõe conteúdo e relações. A implementação visual e o rastreamento
ficam no Barehands; nenhum código AGPL é incorporado a este repositório.
