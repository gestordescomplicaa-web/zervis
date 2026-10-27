# 0042 — Os três modos e o Live: conversa em tempo real, com o revezamento do LIGATIA

- Data: 27/10/2026
- Status: **Aceito** (pedido da pessoa em 27/10/2026, com as quatro escolhas abaixo). Feitas a
  etapa 1 (os modos e o motor do Live no Zé) e a etapa 2 (o cérebro rápido no Live). As etapas 3 e
  4 estão em "Próximos passos".
- Revê o [ADR 0018](0018-modos-de-fala.md) (o Mãos livres vira o Live) e o
  [ADR 0023](0023-voz-ao-vivo.md) (o ao vivo passa a ser em tempo real). Usa a voz do
  [ADR 0041](0041-vozes-da-nuvem.md).

## Contexto

Na voz ao vivo, o Zé funcionava como um walkie-talkie:

- percebia o fim da fala em cerca de 1,05 s (o Smart Turn, consultado uma vez por pausa) ou em
  3 s (o silêncio). Esses números vêm de 13 dias de latências reais;
- não deixava cortar a fala dele, só com o "Ei Zé";
- perdia o que a pessoa dizia enquanto ele pensava.

O LIGATIA conversa como numa ligação porque roda no LiveKit Agents:

- Silero para detectar a voz;
- Deepgram em streaming;
- um detector que decide o fim da fala pelo texto, em português;
- interrupção pela voz.

O detector é da LiveKit Model License e só pode ser usado dentro do LiveKit Agents. O
[ADR 0012](0012-voz-piper-e-escuta-deepgram.md) já tinha registrado isso.

## Decisões da pessoa (27/10/2026)

1. **Três modos:**
   - **Silencioso:** não fala nem ouve.
   - **Normal:** a trava do "Ei Zé". Os avisos são falados e, depois de cada resposta, a pessoa
     pode emendar outra pergunta por 8 s sem repetir o "Ei Zé".
   - **Live:** conversa como numa ligação.
2. **O Mãos livres entra no Live.** As respostas das sessões são lidas e a pessoa responde na hora.
   O nome antigo continua valendo, gravado ou falado ("modo mãos livres").
3. **Live no PC com o cancelador de eco do PipeWire** (etapa 4).
4. **O motor é o LiveKit Agents**, o mesmo do LIGATIA. A pessoa aceitou a licença do detector e
   as cerca de 250 MB de bibliotecas.

## As provas (27/10/2026)

As provas ficaram fora do repositório. Nelas, uma pessoa simulada falou frases em português e o
cérebro foi simulado com tempo fixo.

| | O Zé até aqui | Prova 1 (sala) | Prova 2 (sem sala) | Prova 3 (código do Zé) |
|---|---|---|---|---|
| Perceber que a pessoa terminou | 1,05 s | 0,40–0,58 s | 0,40–0,48 s | 0,15–0,26 s depois de o som parar |
| Cortar falando por cima | só o "Ei Zé" | ✅ ~0,5 s | ✅ ~0,5 s | ✅ |
| Emendar enquanto o Zé pensa | perdia | ✅ | ✅ | ✅ um pedido só ("…França? E da Itália também.") |
| Confirmação ("Aprovo?" → "sim") | — | — | — | ✅ |
| Aviso no meio da conversa | — | — | — | ✅ |
| "Hum" no meio da resposta | ignora | parou 2 s e retomou | parou e não retomou | — |

## Decisão (etapa 1)

1. **O Live troca só os ouvidos, a boca e o revezamento** (`zervis/voz/live.py`). Ele cuida de:
   - Silero, Deepgram nova-3 em pt-BR, o detector multilíngue e a interrupção;
   - uma sessão do LiveKit Agents dentro do processo do Zé, numa thread própria, sem sala nem
     worker. O áudio entra e sai pelo WebSocket da voz, que o app e o navegador já usam;
   - o detector, que roda num executor local, porque o do plugin pede o contexto de um worker.

   O resto do Zé continua como estava:
   - cada vez da pessoa vira um `FalaAoVivo`, que vale como o `FimDeFala` na máquina de estados;
   - o cérebro, os comandos, as confirmações e os avisos seguem pelo laço;
   - o que o laço manda falar volta para o Live: dentro da vez, vira a resposta dela; fora da vez
     (um aviso), é falado pela sessão.
2. **Interrupção:** quando a pessoa fala por cima, o Live corta a fala e o app recebe o "parar"
   de sempre. A máquina recebe o evento novo `Interrompido` e então:
   - corta a fala;
   - devolve o aviso cortado para a fila;
   - interrompe o cérebro que ainda respondia;
   - devolve a vez à pessoa.

   Numa confirmação, cortar a pergunta já conta como responder. Quando o próprio Zé corta a fala
   (um pedido escrito, o Silencioso), isso não volta como interrupção.
3. **Emendar:** se a resposta não chegou a tocar quando a pessoa voltou a falar, o pedido anterior
   vai junto com o novo.
4. **Fim da fala:** a espera mínima é de 0,4 s, como no LIGATIA. A espera máxima, para uma frase
   pela metade, vem da "Espera" da página Voz: Rápida 1,5 s, Normal 2,0 s, Longa 3,0 s.
5. **Interrupção:** a fala por cima precisa durar 0,5 s. O LiveKit não deixa cortar o agente nos
   primeiros segundos de fala de cada conexão, enquanto o cancelamento de eco se ajusta. O padrão
   dele é 3 s; aqui são 1,5 s, porque o celular e o navegador já chegam com o cancelamento ligado.
6. **A geração antecipada fica desligada.** O pedido vai ao cérebro de verdade, com ferramentas e
   efeito, então pedidos pela metade não podem sair.
7. **Quando o Live liga:** com a voz conectada ao vivo pelo WebSocket, que é o navegador ou o app
   no modo "Ao vivo". Sem o modelo, sem a chave do Deepgram ou se a sessão não abrir, a voz ao
   vivo segue pelo recorte de sempre, e o registro diz por quê. O modelo (cerca de 9 MB, revisão
   fixa do plugin) é baixado na primeira subida e por `python -m zervis.preparar`, para a pasta
   de modelos do Zé (`modelos/hf`). Ele fica fora do repositório.
8. **A latência de cada turno** registra `fim_por: "live"`, com o fim da fala e o fim da vez,
   para comparar com o recorte.

## Etapa 2: o cérebro rápido no Live (27/10/2026)

A via rápida (`zervis/cerebro/rapido.py`, desde 09/10/2026) já fazia o que o Live pede:
- a conversa simples vai a um motor leve, com a persona enxuta;
- o que precisa de ferramenta passa ao cérebro completo, com um "Deixa eu ver." para não ficar calado.

Faltava ela valer na hora certa. Decisões da pessoa:

1. **Só no Live** (`via_rapida.quando = "live"`, o padrão; "sempre" é a outra opção). No Normal e
   no teclado, tudo segue para o cérebro completo, como antes. Quando o Live conecta ou sai, o
   núcleo troca só o motor rápido (`religar`), sem reiniciar o cérebro completo, em segundo plano.
2. **Assinatura ou API, as duas.** A página Modelos → Respostas rápidas escolhe o motor e o botão
   Testar mede a primeira palavra. Primeira palavra medida nesta máquina em 27/10/2026, com o
   motor já aberto:

   | Motor (assinatura, sem custo extra) | Primeira palavra |
   |---|---|
   | Claude Sonnet 5.5 (`plano`) | 0,8 a 1,2 s |
   | Codex GPT-6 Luna (`codex`) | 1,1 a 2,3 s |
   | Claude Haiku 4.5 (`plano`) | 2,5 a 3,2 s |

   Uma API direta (OpenAI, OpenRouter, Anthropic, ponte) costuma ser mais rápida, por não passar
   pelo programa do agente. A pessoa pode comparar pelo Testar quando tiver uma chave.
3. **Concordar não é pedido no Live:** "entendi", "beleza", "tá bom" e "certo" sozinhos (até três
   palavras) não vão ao cérebro. No teste, "Entendi." foi tomado como pedido e ligou o modo
   manutenção. Se a última fala do Zé foi uma pergunta, a concordância é a resposta e segue.

## Consequências

- Mais cerca de 250 MB de bibliotecas: livekit-agents, transformers e av. O Live importa o pacote
  na subida, o que leva cerca de 1,3 s, e carrega o modelo em segundo plano.
- O detector não é aberto. É grátis e permite uso comercial, mas só dentro do LiveKit Agents. Quem
  não quiser usá-lo fica com a voz ao vivo pelo recorte.
- Com o Live, o Deepgram recebe o áudio durante toda a conexão ao vivo. Antes, era só durante a
  escuta, e no ao vivo o recorte já ouvia o tempo todo.
- O app do celular ainda fecha o microfone enquanto o Zé fala. Até a etapa 3, cortar a fala pelo
  app só funciona com o "Ei Zé". O navegador já manda o microfone sem parar.

## Próximos passos

- **Etapa 3, app e navegador:**
  - o microfone ligado durante a fala, com o cancelamento de eco do Android;
  - pausar e retomar no aparelho, para o "hum" virar só uma pausa (`resume_false_interruption`);
  - os três modos na notificação do app.
- **Etapa 4, Live no PC:** o cancelador de eco do PipeWire para o microfone do computador.
