# Os conceitos do Zé (09/10/2026, proposta)

Um Zé enxuto: poucos conceitos, cada um com **uma** pergunta que responde, **um** lugar no
código, **um** lugar nos dados e **uma** seção no painel. Se uma coisa nova não cabe em
nenhum, ela provavelmente é parte de um deles.

## Os oito

| Conceito | Responde | É | Não é |
|---|---|---|---|
| **Conversa** | "o que eu falei com o Zé?" | O fio com o Zé, por voz ou texto, com data e hora. | Um pedido a um agente (isso é sessão). |
| **Voz** | "como eu falo com ele?" | O canal da conversa: modo chamado ("Ei Zé") e modo tempo real (como uma ligação). | Uma lista de coisas: não guarda nada, só leva e traz. |
| **Foco** | "no que **eu** estou?" | As frentes do usuário: o que ele começou, com o próximo passo; no máximo três ativas. | Trabalho de agente; um lembrete. |
| **Sessão** | "quem está trabalhando no quê?" | Um agente de código com uma pasta e a sua conversa. Cada pedido feito a ela é uma **tarefa**. | Uma frente do usuário (uma frente pode ter sessões). |
| **Tarefa** | "o que eu pedi para a sessão?" | Um pedido dentro de uma sessão, com começo, fim e resumo falado. Não vive solta. | Algo agendado (isso é automação). |
| **Automação** | "o que roda sozinho, e quando?" | Algo no tempo: **lembrete** (só fala) ou **rotina** (faz: pergunta ao Zé, manda uma tarefa a uma sessão). | Uma frente; uma memória. |
| **Memória** | "o que o Zé sabe?" | **Curta** (fatos aprovados sobre o usuário e sobre o Zé, em toda conversa) e **longa** (conversas, linha do tempo, notas do dia e o ai-memory, buscados quando precisa). | Um procedimento (isso é skill). |
| **Skill** | "como se faz isso do jeito do usuário?" | Um procedimento escrito que o Zé (ou uma sessão) lê antes de agir. | Um fato (isso é memória). |

E a base de tudo: **Projeto** é uma pasta. Frentes, sessões e o ai-memory se ligam pelo projeto.
**Conector** (MCP) é a porta do Zé para outros sistemas (GitHub, agenda, navegador...): um
servidor MCP, local ou remoto, com cada ferramenta livre, com aprovação falada ou bloqueada. Não
é um conceito de uso, é encanamento: o Zé e as skills usam os conectores para agir.

## Como se ligam

```
o usuário ──voz/texto──▶ Conversa ──▶ Zé (cérebro: via rápida + completo)
                                     │ lê ▶ Memória (curta sempre, longa quando precisa)
                                     │ lê ▶ Skills (antes de agir)
                                     │ anota ▶ Foco (frentes do usuário)
                                     │ cria/agenda ▶ Automação ──no horário──▶ fala ou Tarefa
                                     └ delega ▶ Sessão (projeto) ──▶ Tarefa ──fim──▶ aviso falado
                                                                     └▶ ai-memory do projeto
```

## Onde mora cada um

| Conceito | Código | Dados (`~/.local/share/zervis/`) | Painel |
|---|---|---|---|
| Conversa | `zervis/memoria/conversas.py` | `conversas/` | Início (e Conversa, na fatia 2) |
| Voz | `zervis/voz/`, `zervis/cerebro/rapido.py` | — | Voz |
| Foco | `zervis/foco/` | `foco/` | Foco |
| Sessão e Tarefa | `zervis/oficina/sessoes.py` | `sessoes/` | Sessões |
| Automação | `zervis/automacoes/` | `automacoes/` | Automações |
| Memória | `zervis/memoria/` | `memoria/`, `linha-do-tempo.jsonl`, `dias/`, ai-memory | Memória |
| Skill | `zervis/habilidades/skills.py` | `skills/` | Skills |
| Conector | `zervis/cerebro/mcp_externo.py`, `conectores.py` | `~/.config/zervis/mcp.toml`, `mcp-painel.json` | Conectores |

## O que arrumar para chegar nisso

1. **Tarefa do Orca vira tarefa de sessão.** A `Oficina` de hoje guarda "tarefas" delegadas ao
   Orca; com a oficina própria, delegar = mandar uma tarefa a uma sessão (o Orca vira um motor).
2. **Automação ganha "rotina".** Hoje há `lembrete` e `pergunta`; a rotina que manda uma tarefa
   a uma sessão ("toda segunda, rode os testes do Ligatia") fecha o ciclo.
3. **Foco se liga a sessões pelo projeto:** a frente mostra as sessões do projeto, e o fim de
   uma tarefa já atualiza o próximo passo (hoje isso acontece só com o Orca).
4. **Sugestões de aprendizado** (`pendencias.json`) são propostas de **Memória** ou de
   **Skill**: aparecem nessas seções para aprovar, não num lugar à parte.
5. **O painel em três grupos:** *Agora* (Início, Foco, Conversa), *Trabalho* (Sessões,
   Automações) e *O Zé* (Memória, Skills, Conectores, Cérebro e chaves, Voz); Imersão e
   Configurações à parte.
