# 08 — Análise: ruxakK/jarvis-voice-butler

Data: 06/10/2026. Repositório: https://github.com/ruxakK/jarvis-voice-butler (54 estrelas, 3 commits,
criado em 07/09/2026, último commit em 19/09/2026). Lido numa cópia isolada, sem executar nada.

## O que é

Um "mordomo" de voz em inglês que controla um navegador. É montado quase todo sobre os
**modelos oficiais do LiveKit**:
- `jarvis_new/src/` — o agente em Python (~850 linhas): `agent.py`, `tools.py`, `browser.py`, `prompts.py`.
- `jarvis_new/frontend/` — front web em Next.js (modelo `agent-starter-react` do LiveKit, MIT).
- `agent-starter-flutter/` — app de celular em Flutter (modelo do LiveKit, MIT).

### Como funciona
- **Cérebro e voz juntos:** o Gemini Live (`gemini-3.1-flash-live-preview`, voz "Enceladus") é um
  modelo *realtime*: recebe o áudio e devolve áudio direto, sem etapa separada de transcrição e síntese.
- **LiveKit Agents:** sessão com detector de fim de turno (`TurnDetector`), interrupção adaptativa
  (distingue interrupção de um "uhum") e geração antecipada enquanto o usuário termina de falar.
- **Mãos:** 11 ferramentas de navegador com Playwright (abrir URL, buscar, ler, inspecionar, clicar,
  digitar, rolar, tecla, voltar, captura) e `confirm_browser_action` para ações sensíveis.
- **Testes:** avaliações do agente com um modelo "juiz" (`session.run(...).expect...judge(...)`),
  além de testes do navegador e do prompt.

### Dependências e custos
- **Nuvem obrigatória:** chave do Gemini (Google) e um servidor LiveKit (`LIVEKIT_URL`, `API_KEY`,
  `API_SECRET`, pensado para o LiveKit Cloud), redução de ruído `ai_coustics` (plugin pago na nuvem do LiveKit).
- Partes do `browser.py` são específicas de Windows (foco de janela por `hwnd`).
- **Sem licença no repositório:** por padrão, todos os direitos reservados. **Não copiar código.**
  Os dois modelos do LiveKit dentro dele (front React e app Flutter) são MIT e podem ser usados
  direto da fonte oficial do LiveKit.

## Comparação com o JARVIS

| Aspecto | voice-butler | JARVIS (plano) |
|---|---|---|
| Onde roda | Nuvem (Gemini + LiveKit Cloud) | Local, na máquina; só o cérebro chama o provedor |
| Cérebro | Gemini Live (áudio↔áudio), por chave de API | Claude/Codex por login de assinatura |
| Voz | A do Gemini, em inglês | Cadu local em pt-BR + normalizador de fala |
| Ativação | Sessão aberta no app (sem palavra de ativação) | "Hey Orca" pessoal + rosto conectado |
| Mãos | Navegador isolado (Playwright) | Máquina inteira (Omarchy), Orca, navegador depois |
| Memória e skills | Não tem | Núcleo do projeto |
| Automações | Não tem | Núcleo do projeto |
| Segurança das ações | Lista de palavras + o **próprio modelo** chama a confirmação | Confirmação falada verificada pelo núcleo, níveis de risco |
| Celular | App Flutter pronto do LiveKit | Última fase (LiveKit local + Tailscale) |

## O que vale levar (ideias)

1. **Regras de saída para voz no prompt**: texto puro, uma a três frases, uma pergunta por vez, não
   recitar identificadores, explicar a falha uma vez e propor alternativa. Já temos isso na persona
   e no `fala.py`; vale conferir se falta algo (ex.: "não revelar nomes de ferramentas").
2. **Detector de fim de turno semântico e interrupção adaptativa** do LiveKit: hoje o JARVIS
   decide o fim da fala por silêncio (2 s). Um detector de turno pode cortar a espera pela metade.
   Avaliar na Fase 1 se dá para usar o modelo de turno do LiveKit **localmente**, sem a nuvem.
3. **Geração antecipada**: começar a pensar enquanto o usuário ainda termina a frase.
4. **Avaliações com modelo juiz** como teste de comportamento da persona ("responde curto?",
   "pede confirmação antes de ação sensível?"). Entra como suíte opcional na Fase 2.
5. **Navegador isolado e criado só quando necessário** (Playwright, contexto por sessão, fechado
   ao fim), com validação de URL (só http/https, sem credenciais embutidas): boa base para uma
   futura ferramenta `navegador` do JARVIS.
6. **App Flutter do LiveKit (MIT)** como ponto de partida do cliente Android na fase do celular,
   se o navegador do Android cortar o microfone com a tela bloqueada.

## O que não levar

- Dependência de nuvem para voz e transporte.
- **Confirmação decidida pelo próprio modelo** (`confirm_browser_action` é chamada pelo LLM depois
  que ele "acha" que o usuário confirmou). No JARVIS a confirmação é verificada pelo núcleo, a
  partir da transcrição da fala do usuário, nunca pela palavra do modelo.
- *Easter eggs* e regras fixas de frase no prompt.
- Modelo *realtime* áudio↔áudio como cérebro: perderia o Cadu, o normalizador pt-BR, a
  independência de provedor e a aprovação por voz com rechecagem.

## Conclusão

É uma boa demonstração de voz com LiveKit e controle de navegador, mas é outro produto: um
assistente de navegador na nuvem, sem memória, sem skills e sem automações. Confirma duas
escolhas nossas (LiveKit como transporte para o celular; regras de fala no prompt) e traz três
ideias concretas para a voz: fim de turno semântico, interrupção adaptativa e geração antecipada.
