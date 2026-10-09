# 0008 — OmniRoute local como provedor do cérebro

- Data: 06/10/2026
- Status: **Aceito** (pedido do usuário; Prova 4 da Fase 0 confirmou que funciona)
- Refina: [0002](0002-cerebro-por-sdk-de-agente.md) e [0007](0007-cerebro-base-rapido-e-codificacao-no-orca.md)

## Contexto
O usuário já roda o **OmniRoute** (`omniroute.service`, gateway local de IA, só em loopback,
`http://127.0.0.1:20128`). Ele junta as contas conectadas no painel atrás de rotas como
"Combo Supremo" e `auto/*`, e o JARVIS anterior já planeja por ele. O pedido: que o
JARVIS novo também possa usar o OmniRoute como **motor de decisão** (o cérebro base que decide e
chama as ferramentas).

O OmniRoute fala três formatos: OpenAI (`/v1/chat/completions`), Anthropic (`/v1/messages`) e
Responses (`/v1/responses`). A chave fica em `OMNIROUTER_API_KEY` (hoje no `.env` do perfil
de um perfil do Hermes, compartilhada com o JARVIS anterior).

## Decisão
1. O OmniRoute entra como **terceiro provedor do cérebro**, ao lado de Claude (assinatura) e
   Codex (app-server), escolhido na config (`provedor = "omniroute"`) e por voz.
2. Ele **não ganha implementação própria**: é o mesmo `ClaudeBrain` (Agent SDK) com o ambiente
   do processo do CLI apontado para o roteador:
   `ANTHROPIC_BASE_URL=http://127.0.0.1:20128`, `ANTHROPIC_AUTH_TOKEN=<chave>`,
   `ANTHROPIC_API_KEY=""`, `ANTHROPIC_SMALL_FAST_MODEL=<rota>`, modelo = a rota.
   Assim ele herda de graça o que o SDK já dá: sessão contínua, fala por frase, ferramentas MCP do
   JARVIS e aprovação pelo `can_use_tool`.
3. A rota padrão é configurável; a sugerida para conversa é a mais rápida medida
   (`auto/subscription`), e "Combo Supremo" fica disponível para pedidos que pedem mais raciocínio.
4. O endereço tem de ser loopback (mesma regra do JARVIS anterior); fora disso o
   `jarvisd` recusa a config.
5. A chave segue a regra de segredos do [06](../06-qualidade.md): variável de ambiente do serviço
   (`EnvironmentFile=` apontando para o `.env` existente, sem copiar o valor) ou chaveiro. Nunca
   em `config.toml`, log ou memória.
6. **`permission_mode="default"` sempre explícito** em qualquer provedor (ver Prova 4 abaixo).

## Resultado da Prova 4 (06/10/2026)
`provas/prova4_omniroute.py` e `provas/prova_ferramentas.py`, mesma persona e pedidos da Prova 1.
Todas as rotas testadas foram atendidas pelo modelo `gpt-6-luna`.

| Caminho | Rota | 1ª frase (1º / 2º turno) |
|---|---|---|
| Direto, `/v1/chat/completions` | Combo Supremo | 10,4 / 10,4 s (resposta inteira de uma vez) |
| Direto | `auto/best-fast` | 5,3 / 1,8 s |
| Direto | `auto/subscription` | 2,1 / 1,3 s |
| Agent SDK → `/v1/messages` | `auto/subscription` | 1,5 / 3,8 s |
| Agent SDK → `/v1/messages` | Combo Supremo | 2,9 / 3,3 s |

- Pelo Agent SDK, o modelo **chamou as ferramentas MCP** do JARVIS (hora e volume) nas duas rotas.
  O CLI só avisa `unrecognized_model` no stderr, sem efeito.
- **Falha de segurança encontrada e contornada:** sem `permission_mode` explícito, via OmniRoute a
  ferramenta que exige aprovação **rodou sem passar pelo `can_use_tool`** (na assinatura o mesmo
  código perguntou). Com `permission_mode="default"` a aprovação voltou a ser pedida e a negação
  foi respeitada (ferramenta não executou). Causa no CLI não confirmada. A Fase 2 precisa de um
  teste de regressão por provedor: "ferramenta com aprovação ⇒ `can_use_tool` chamado".
- Latência variou bastante entre rodadas (amostras pequenas); ainda acima da meta de ~1 s na
  primeira frase em parte dos casos. A rota e o tempo limite ficam na config.

## Consequências
- Um provedor a mais sem código novo de cérebro; o teste de aprovação passa a rodar para os três.
- O OmniRoute vira dependência opcional: se o serviço estiver parado, o `jarvisd` avisa uma vez e
  usa o provedor de reserva configurado (nunca troca em silêncio).
- **A verificar:** qual conta o OmniRoute usa para `gpt-6-luna`. Se for a mesma assinatura
  ChatGPT Plus do Codex, os dois provedores dividem a cota semanal (88% usada em 06/10/2026).

## Implementação (Fase 2, 06/10/2026)
- `provedor = "omniroute"` em `[cerebro]`, com `omniroute_endereco` (recusado fora de http em
  loopback), `omniroute_rota` (padrão `auto/subscription`), `tempo_limite_s` (vale para todo
  provedor: sem nenhuma mensagem do modelo nesse prazo, o pedido falha e a sessão é refeita) e
  `reserva` (`claude` ou `eco`).
- **Chave:** em vez de `EnvironmentFile=` com o `.env` inteiro do Hermes (que poria dezenas de
  outros segredos no ambiente do `jarvisd` e do CLI), o `jarvisd` lê só a linha
  `OMNIROUTER_API_KEY` desse arquivo (`omniroute_arquivo_chave`), ou a variável de ambiente se
  existir. O valor não vai para log nem para a config.
- Se o OmniRoute estiver parado ou sem chave ao subir, o `jarvisd` registra o aviso e usa a reserva;
  o `status.json` mostra o provedor em uso. O aviso falado entra com a fila de avisos (Fase 7).
- Regressão de segurança: `tests/test_omniroute.py` confere `permission_mode="default"` e
  `can_use_tool` nos dois provedores; `provas/prova_aprovacao_provedores.py` confere com modelo real.

### Prova de aprovação com modelo real (06/10/2026)
| Provedor | Pesquisa aprovada | Pesquisa negada | 1º texto (aprovada / negada) |
|---|---|---|---|
| Claude (assinatura, Sonnet 5.5) | 2 perguntas, respondeu em 15 s | 1 pergunta, respeitou | 1,8 / 1,8 s |
| OmniRoute (`auto/subscription`) | **8 perguntas**, respondeu em 78 s | 1 pergunta, respeitou | 5,9 / 8,2 s |

A falha da Fase 0 não se repetiu: toda ferramenta passou pelo `can_use_tool` e a negação foi
respeitada. Mas, para conversa por voz, o OmniRoute ficou bem pior: o modelo da rota repetiu a
pesquisa seis vezes (seriam oito perguntas faladas para um pedido), demorou de 3 a 5 vezes mais
para começar e respondeu com link em Markdown, contra a persona. **O Claude segue como padrão;**
o OmniRoute fica disponível na config para quando a assinatura estiver no limite.
