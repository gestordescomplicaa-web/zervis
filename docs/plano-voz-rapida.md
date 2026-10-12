# Plano — voz rápida (09/10/2026; etapas 0 e 1 feitas)

Pedido do usuário: o Zé responder por voz tão rápido quanto o agente do Ligatia, sem trocar o
Piper nem o Deepgram, e **agnóstico de provedor**. Provedores de primeira classe:

1. **Anthropic** pelo plano (login do Claude) ou pela chave de API;
2. **OpenAI** pelo plano (login do ChatGPT, o do Codex) ou pela chave de API;
3. **OpenRouter** pela chave;
4. **Ponte**: qualquer proxy no formato da OpenAI (OmniRoute, LiteLLM ou outro), com endereço
   e chave próprios. O OmniRoute local é só um exemplo dessa opção, não a base.

## Onde o tempo vai hoje (medido em 08 e 09/10/2026)

| Etapa | Zé hoje | Ligatia |
|---|---|---|
| Fim da fala até fechar o pedido | pausa de 0,64 s + Smart Turn | 0,4 s de silêncio (Silero) |
| Transcrição | 0,2 s (Deepgram em fluxo) | igual |
| Cérebro até a primeira palavra | 1,4 a 2,2 s; 4 a 4,7 s com ferramenta | 0,3 a 0,5 s (mini pela API) |
| Piper até o primeiro som | ~0,2 s | ~0,1 s (1 thread, aquecido) |
| **Total numa resposta simples** | **~2,5 a 3 s** | **~1 s** |

Medições do cérebro pela assinatura, prompt curto, sem ferramentas (09/10/2026):
Sonnet 0,7 a 1,0 s; Haiku 0,95 a 1,2 s; Codex `gpt-6-luna` 1,0 a 1,9 s. O Haiku pela API
direta fica em 0,15 a 0,35 s: a diferença é o programa intermediário (Claude Code / Codex),
não o modelo. Com o prompt completo do Zé (persona, memória, ~40 ferramentas) soma mais 0,4
a 1 s.

## Linguagem

O que pesa já é nativo ou remoto: Piper, VAD e Smart Turn rodam no onnxruntime (C++);
Deepgram e o modelo estão na rede. A orquestração em Python custa dezenas de milissegundos
num orçamento de um segundo. Reescrever o núcleo em Rust ou Go não tira o segundo e meio do
cérebro. Fica em Python; a etapa 0 mede a orquestração e, se ela passar de 50 ms por turno, o
laço de áudio vira candidato a Rust. A escolha de linguagem pesa mesmo no painel prático
(fase própria, depois).

## Etapas (cada uma medida antes e depois, commit próprio)

0. **Medir cada turno.** Uma linha por turno com fim da fala, pedido fechado, transcrito,
   primeiro token, primeiro som; resumo diário com mediana e p95. É a régua de tudo.
1. **Via rápida.** Um cérebro de conversa novo (`jarvis/cerebro/rapido.py`), em fluxo, com
   prompt enxuto (persona curta, memória curta, data e hora, a última conversa) e só
   ferramentas de leitura rápida. Quando precisa de mais (ferramenta, projeto, máquina,
   raciocínio longo), ele não tenta: passa ao cérebro completo (Claude pelo SDK, como hoje),
   que recebe a mesma conversa. Três motores atendem os provedores:
   - **HTTP no formato OpenAI**: chave da OpenAI, OpenRouter e a ponte (um código só, muda o
     endereço e a chave);
   - **HTTP no formato Anthropic** (Messages): chave da Anthropic;
   - **plano**: Claude pelo SDK com o prompt enxuto (o login do Claude só funciona por ele) e
     Codex pelo `codex app-server` (login do ChatGPT), medido antes de entrar.
   As chaves ficam em arquivos próprios (`chmod 600`), nunca na config nem no repositório.
2. **Aviso na hora.** Quando a resposta vai ao cérebro completo ou chama uma ferramenta, o Zé
   fala uma frase curta já sintetizada ("deixa eu ver", "um instante") em vez de ficar calado.
3. **Começar antes.** Como o `preemptive_generation` do Ligatia: na pausa, com a transcrição
   final do Deepgram, a via rápida já começa; se o usuário continuar falando, a resposta é
   descartada. Só na via rápida, que não muda nada no mundo (mesma regra do Ligatia: sem
   antecipação quando há ferramenta que altera estado).
4. **Fim de fala mais curto.** Pausa de 0,64 s para ~0,45 s com o Smart Turn, medindo os
   cortes indevidos na etapa 0 antes de manter.
5. **Piper enxuto.** Uma thread, execução sequencial, aquecido ao subir, e as frases curtas
   frequentes ("deixa eu ver", "pronto", "oi, o usuário") guardadas prontas.

Meta: primeira fala em ~1 s com chave de API e em ~1,5 s só com a assinatura, nas conversas
simples; nos pedidos com ferramenta, a frase de aviso em menos de 1 s.

## Fora deste plano

O painel prático (menu lateral, clique e texto, voz opcional; o modo imersivo fica como opção)
é a fase seguinte, desenhada com o usuário antes de começar.

## Zona protegida

As etapas 1 e 2 tocam `jarvis/config.py` (a seção da via rápida) e talvez
`jarvis/cerebro/claude.py` (o aviso antes da ferramenta). Precisam da aprovação do usuário.

## Etapa 1 feita (09/10/2026)

`jarvis/cerebro/rapido.py` (motores e `Roteado`), `jarvis/persona/RAPIDO.md`, `[via_rapida]` na config,
testes em `tests/test_via_rapida.py`. Medido pelo teclado, mesmo caminho até o primeiro som:
cérebro de 3.144 ms (completo, mediana de 09/10) para 977 ms (via rápida pelo plano, Sonnet);
primeiro som em 1.562 ms. Medidos também os modelos "rápidos" pelos gateways do OmniRoute
(1,3 a 5 s): lentos; o ganho grande depende da chave de API direta.

Próximos passos: chave de API (anthropic ou openai) para medir a meta de ~1 s por voz; falar
a primeira oração antes da frase inteira (formação da frase: ~340 ms); etapas 3 a 5.
