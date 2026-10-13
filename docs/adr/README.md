# Decisões de arquitetura (ADRs)

Uma decisão por arquivo, numerada, nunca apagada. Mudou de ideia? Novo ADR que **substitui** o antigo
e o antigo ganha "Substituído por NNNN" no status.

| Nº | Decisão | Status |
|---|---|---|
| [0001](0001-nucleo-proprio-com-mecanismos-do-hermes.md) | Núcleo próprio, copiando mecanismos do Hermes | Aceito |
| [0002](0002-cerebro-por-sdk-de-agente.md) | Cérebro pelos SDKs oficiais de agente, ferramentas por MCP | Aceito (Provas 1 e 2 ok) |
| [0003](0003-front-como-interruptor.md) | Janela do Barehands como liga/desliga | Aceito |
| [0004](0004-ponte-de-audio-livekit-adiada.md) | Ponte de áudio LiveKit fora do núcleo por enquanto | Substituído por 0005 |
| [0005](0005-celular-por-livekit-e-tailscale.md) | Celular como rosto remoto: LiveKit local + Tailscale | Proposto, última fase |
| [0006](0006-orca-continua-como-oficina.md) | O Orca continua como oficina; alternativas avaliadas | Aceito |
| [0007](0007-cerebro-base-rapido-e-codificacao-no-orca.md) | Cérebro base rápido; codificação com os agentes do Orca | Aceito |
| [0008](0008-omniroute-como-provedor-do-cerebro.md) | OmniRoute local como provedor do cérebro | Aceito |
| [0009](0009-conversa-continua-com-ok.md) | Conversa contínua: "ok" encerra, sem repetir "Hey Orca" | Aceito |
| [0010](0010-troca-de-cerebro-e-baterias.md) | Troca de cérebro pelo JARVIS e baterias no Barehands | Aceito |
| [0011](0011-orcamento-de-tokens.md) | Orçamento de tokens: medir, sessão nova após pausa, regras para skills/MCP | Aceito |
| [0012](0012-voz-piper-e-escuta-deepgram.md) | Voz pelo Piper (Cadu, CC0) e escuta pelo Deepgram em streaming | Aceito (o Piper à parte foi substituído pela 0013) |
| [0013](0013-agpl-e-piper-dentro-do-ze.md) | Licença AGPL-3 e o Piper dentro do Zé | Aceito |
| [0014](0014-imersivo-dentro-do-ze.md) | O modo imersivo (holograma, Núcleo, mãos) dentro do Zé | Aceito |
| [0015](0015-cerebro-agente-sem-orca.md) | Três camadas (voz rápida, cérebro, sessões); cérebro e sessões são agentes (Claude Code ou Codex), sem o Orca; ai-memory comum | Aceito |
| [0016](0016-continuidade-entre-contas-e-agentes.md) | Continuidade entre contas e agentes (testada), ai-memory embutido | Aceito |
| [0017](0017-terminal-real-nas-sessoes.md) | A sessão de código é o terminal real do agente (xterm.js), com os comandos dele | Aceito |
| [0018](0018-modos-de-fala.md) | Modos de fala (Silencioso, Avisos, Mãos livres): quando o Zé fala sem ser chamado | Aceito (o chamado no Silencioso mudou na 0022) |
| [0019](0019-autorizacao-http-do-imersivo.md) | Pedidos e leituras do imersivo autorizados por instância | Aceito |
| [0020](0020-contas-na-voz-e-no-cerebro.md) | Contas Claude/Codex na voz e no cérebro, com alternativas antes de qualquer ação | Aceito |
| [0021](0021-rostos-e-escuta.md) | Rostos e a escolha "Escuta": a voz sem depender do Hyprland | Aceito |
| [0022](0022-ativacao-e-segurar-para-falar.md) | Ativação ("Ei Zé" ou só o botão) separada do modo de fala; segurar para falar | Aceito (ponto 3 ajustado pela 0023) |
| [0023](0023-voz-ao-vivo.md) | Voz ao vivo: "Conectar voz" ouve sem parar até desconectar | Aceito |
| [0024](0024-voz-pelo-https.md) | A voz do navegador dentro do HTTPS do painel (WebSocket) | Aceito |
| [0025](0025-atividade-e-auto-aperfeicoamento.md) | Atividade e auto-aperfeiçoamento: o que o Zé fez e onde tropeçou | Aceito (camada 1) |
| [0026](0026-sessao-de-auto-desenvolvimento.md) | A sessão de auto-desenvolvimento do Zé, com essência e travas | Aceito (passos 1 e 2) |
