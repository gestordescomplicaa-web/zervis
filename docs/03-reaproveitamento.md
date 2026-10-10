# 03 — Reaproveitamento

Data: 06/10/2026. O que entra no projeto novo, de onde vem, em que estado está e sob qual licença.

## Regra de licenças

| Origem | Licença | O que podemos fazer |
|---|---|---|
| JARVIS atual (`VIBE-CODING/jarvis`) | nosso | Copiar e adaptar livremente. |
| Hermes Agent (`~/.hermes/hermes-agent`) | **MIT** | Copiar trechos com aviso de autoria (cabeçalho citando Nous Research + MIT) em `THIRD_PARTY.md`. |
| Barehands | **AGPL-3.0** | Embutido em `jarvis/imersivo/` (ADR 0014), com os avisos de autoria. |
| backtalk, ai-visualizer (jaredrhod) | **AGPL-3.0** | Compatíveis com a licença do Zé; código copiado mantém o aviso de autoria e entra em `THIRD_PARTY.md`. |
| Piper (`piper-tts`) | **GPL-3.0** | Dependência Python, dentro do processo (ADR 0013). |
| ai-memory-vault (jaredrhod) | CC BY-SA 4.0 | Só ideias (estrutura de notas); se copiar texto de template, citar e manter a licença. |

## 1. Do JARVIS atual (1.600 linhas Python, 37 testes passando em 06/10/2026)

| Módulo | Faz | Destino no projeto novo | Ajustes |
|---|---|---|---|
| `fala.py` (159) | Normalizador de fala pt-BR: números, datas, horas, R$, %, versões, caminhos, hashes, siglas com letra | `voz/fala.py` — **levar inteiro com os testes** | Nenhum. É o componente mais maduro. |
| `voice.py` (171) | Pocket TTS "Cadu" com streaming, fila, interrupção, onda do anel | `voz/saida.py` | Separar a interface `Voz` do motor Cadu. |
| `wakeword.py` (45) + `train_wake.py` (125) + `enroll.py` (56) | Detector pessoal "Hey Orca" e seu treino | `voz/ativacao/` | Motor trocável no estilo do Hermes. O modelo fica em `~/.local/share/jarvis-orca/wake/hey_orca.npz`. |
| `listening.py` (58) | Frases de comando, validação do pedido, chamada da transcrição | `voz/escuta.py` | A transcrição usa `voice/transcribe.py` (whisper.cpp/Voxtype com Vulkan): trazer junto e tirar do venv do Hermes. |
| `ring.py` (77) | Estado/cor/onda do anel no Barehands | `rosto/anel.py` | Adicionar estado "inativo". |
| `board.py` (60) | Cards temporários no quadro do Barehands | `rosto/quadro.py` | Já checa se a janela está aberta: vira a base do liga/desliga. |
| `notices.py` (122) | Fila durável de avisos (SQLite), prioridade, expiração, resumo | `avisos/fila.py` | Adicionar estado "pendente enquanto inativo". |
| `aprovacao.py` (179) | Descrição falada + aprovação por voz com confirmação e rechecagem | `oficina/aprovacao.py` | Nenhum na lógica; vale só para sessões do Orca. |
| `orca.py` (76), `agents.py` (41) | CLI do Orca rápida, marcadores de aprovação Claude/Codex | `oficina/orca.py` | Acrescentar orquestração (`worker-start`, caixa de entrada do Run). |
| `lembrar.py` (61) | Busca no ai-memory em todos os projetos | `memoria/historico.py` | Vira ferramenta do cérebro. |
| `brain.py` (100) | Envio ao painel do Orca + espera da resposta | **Não levar.** Substituído pelo cérebro por SDK (ADR 0002). | `speakable()` (limpeza de Markdown) vai para `voz/fala.py`. |
| `core.py` (270) | Laço único: microfone, estados, avisos, voz | Reescrever como máquina de estados explícita | Manter as proteções: eco, autorização por palavra de ativação, uma fala por vez. |
| `persona/JARVIS.md` | Regras de fala e de ação | `persona/JARVIS.md` | Remover a parte "consulte o Orca pela CLI" do texto fixo; vira skill. |
| Skill `fala-natural` | Resumo falado no fim das respostas das sessões | Fica no projeto onde as sessões rodam | O JARVIS lê o bloco "Resumo falado:" dos avisos. |
| `hermes-monitor/orca_monitor.py` | Redutor de estado das sessões do Orca | `oficina/monitor.py` | Testado; manter. |
| `hermes-monitor/calendar_monitor.py` | Leitura da agenda do Omarchy | `automacoes/fontes/agenda.py` | Reativar a agenda que ficou sem dono. |

**Lições já pagas que precisam continuar valendo** (vêm das memórias do projeto):
- `orca terminal send --text --enter` ativa um modo que espera ~8 s; enviar texto e Enter separados.
- A CLI do Orca via node do processo em execução custa 0,14 s (o AppImage, 1,2 s).
- Ler a tela com `--screen`, nunca o stream (perde sobreposições).
- O Cadu manda WAV float32, não PCM16.
- O Claude em modo automático não deixa um agente aprovar o pedido de outro: a tecla sai do núcleo.

## 2. Do Hermes (mecanismos, reimplementados enxutos)

| Mecanismo | Referência no Hermes | Tamanho alvo no JARVIS |
|---|---|---|
| Memória curta com limite + ferramenta add/replace/remove | `tools/memory_tool.py`, `tools/memory_tool_store.py` | ~250 linhas |
| Varredura de segurança do conteúdo de memória/skill | `_scan_memory_content` | ~60 linhas + testes |
| Skills: listar, ver, escrever com pendência e diff | `tools/skills_tool.py`, `tools/skill_manager_tool.py` | ~400 linhas |
| Revisão em segundo plano (prompts e critérios) | `agent/background_review.py` linhas ~353–540 | prompts adaptados + ~150 linhas |
| Curadoria determinística (uso, stale, arquivo) | `agent/curator.py`, `tools/skill_usage.py` | ~120 linhas |
| Jobs agendados, escrita atômica, `last_status` fechado | `cron/jobs.py`, `cron/scheduler.py` | ~400 linhas |
| Hooks de eventos internos | `gateway/hooks.py` | ~80 linhas |

## 3. Da pilha jaredrhod (só ideias)

- **backtalk:** cérebro numa sessão própria pelo Agent SDK; fala frase a frase durante a geração;
  aprovação pelo *callback* do SDK ("Sim, não ou detalhes?"); console de voz por frases exatas;
  retomar a última sessão ao abrir; som de "pensando" para a pausa não parecer queda.
- **ai-visualizer:** rostos leves só com navegador, sem câmera — opção para quando o Barehands
  (câmera) não for necessário. Os dois leem o mesmo "barramento de sinais" em arquivos.
- **ai-memory-vault:** notas diárias, uma nota por tarefa recorrente dizendo o que ler antes
  ("priming"), índice por pasta e regras de "checkpoint" para manter a memória viva.
