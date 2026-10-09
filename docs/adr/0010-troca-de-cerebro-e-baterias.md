# 0010 — Troca de cérebro pelo JARVIS e baterias no Barehands

- Data: 06/10/2026
- Status: **Aceito** (pedido do usuário)
- Refina: [0008](0008-omniroute-como-provedor-do-cerebro.md)

## Contexto
Trocar de cérebro exigia editar o `config.toml` e reiniciar. O usuário pediu para trocar pelo
próprio JARVIS, por voz ou na interface, e para ver a "bateria" de cada modelo, ou seja, quanto
ainda resta da cota de cada assinatura.

## Decisão
1. **Catálogo fixo** (`jarvis/cerebro/catalogo.py`), escolhido pelo usuário: Claude (Sonnet 5.5
   pela assinatura), GPT (`cx/gpt-6-luna`), Gemini (`agy/gemini-3.1-pro-high`) e Automático
   (`omniroute_rota`). Todos são o mesmo `ClaudeBrain`; os três últimos pelo OmniRoute.
2. **Troca por voz:** verbo + nome ("muda para o GPT", "usa o Gemini", "volta para o Claude"),
   só com palavras de apoio no meio, para "usa o Claude para revisar o código" seguir sendo pedido.
   **No Barehands:** toque no nome na faixa de baixo.
3. A troca abandona o pedido em curso, inicia o cérebro novo e fecha o antigo; um pedido que chega
   no meio espera a troca. A escolha fica em `~/.local/state/zervis/cerebro` e vale depois de
   reiniciar. OmniRoute fora do ar ou sem chave: a troca é recusada com uma frase falada.
4. **Baterias** = quanto resta (0–100%) na janela mais apertada da família:
   - Claude: o `RateLimitEvent` de cada resposta (janelas de 5 h e semana); o último valor fica em
     `limite_claude.json` para sobreviver a reinícios e a períodos com outro cérebro.
   - GPT e Gemini: o cache que o OmniRoute já atualiza sozinho para cada conta conectada
     (`providerLimitsCache` no `storage.sqlite`), **só leitura**, a cada 30 s. A API de cota do
     OmniRoute exige login do painel (a chave de uso recebe 403), por isso o banco.
   - Gemini conta só a cota do `gemini-3.1-pro` (a do catálogo). Cache com mais de 3 h é ignorado.
   - "Como estão as baterias?" responde por voz.
5. **Barehands:** o JARVIS escreve `state/cerebros.json` (mesmo contrato do anel). O `server.py`
   ganhou `GET /cerebros` (arquivo velho = lista vazia) e `POST /cerebro`, que só aceita JSON e um
   id que esteja na lista, e grava `state/escolha.json`; o JARVIS consome o arquivo (clique com mais
   de 30 s é ignorado). As mudanças ficam no próprio Barehands (AGPL), marcadas com
   `barehands-jarvis:` como os ajustes anteriores; nada do código dele vem para este repositório.

6. **Modelo à vista:** cada nome no Barehands mostra embaixo o modelo (Sonnet 5.5, GPT-6 Luna,
   Gemini 3.1 Pro). No ativo vale o que respondeu de fato (`AssistantMessage.model`); no
   Automático, o último que o OmniRoute escolheu. A frase da troca e o relatório falam o modelo.

## Consequências
- Ler o banco do OmniRoute depende de um formato interno: qualquer mudança vira "sem dado", nunca
  falha do JARVIS. Se o OmniRoute ganhar uma API de cota com a chave de uso, trocar por ela.
- Bateria do Claude só aparece depois da primeira resposta dele.

### Prova com modelo real (06/10/2026, `provas/prova_aprovacao_provedores.py`)
| Cérebro | 1º texto (aprovada / negada) | Perguntas de aprovação num pedido de pesquisa |
|---|---|---|
| Claude | 1,8 / 1,8 s | 2 |
| GPT (`cx/gpt-6-luna`) | 4,0 / 1,8 s | **11** |
| Gemini (`agy/gemini-3.1-pro-high`) | 9,3 / 21,0 s | 2 |

A aprovação foi pedida sempre e o "não" foi respeitado em todos. Para conversa, o Gemini é lento
demais, e o GPT repete a pesquisa muitas vezes, o que vira uma pergunta falada por repetição.
