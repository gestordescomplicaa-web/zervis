# Decisões de arquitetura (ADRs)

Uma decisão por arquivo, numerada, nunca apagada. Mudou de ideia? Novo ADR que **substitui** o antigo
e o antigo ganha "Substituído por NNNN" no status.

Os ADRs ficam como foram escritos, com a data. Os mais antigos chamam o Zé de JARVIS (o nome até
08/10/2026) e o chamado de "Hey Orca" (hoje, "Ei Zé").

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
| [0025](0025-atividade-e-auto-aperfeicoamento.md) | Atividade e auto-aperfeiçoamento: o que o Zé fez e onde tropeçou | Aceito (camadas 1 e 2) |
| [0026](0026-sessao-de-auto-desenvolvimento.md) | A sessão de auto-desenvolvimento do Zé, com essência e travas | Aceito |
| [0027](0027-regras-de-fala.md) | Regras de fala: quando o Zé fala sozinho, sobre o quê e quantas vezes | Aceito |
| [0028](0028-manutencao-estado-do-ze.md) | Manutenção, um estado do Zé: o centro do próprio código | Aceito |
| [0029](0029-central-de-avisos.md) | Central de avisos: como o Zé narra várias sessões pela voz | Aceito |
| [0030](0030-assistente-de-mensagens-whatsapp.md) | Assistente de mensagens do WhatsApp: o Zé avisa o que é importante para você | Proposta (fonte substituída pelo 0031) |
| [0031](0031-atendimento-whatsapp-e-telefonia.md) | Atendimento: o Zé atende clientes no WhatsApp e no telefone | Aceito |
| [0032](0032-arquitetura-para-crescer.md) | Arquitetura para crescer: linguagem por papel, núcleo dividido, SQLite e pacotes | Aceito como direção (plano E1 a E7) |
| [0033](0033-pacotes-de-extensao.md) | Pacotes de extensão: o Zé ganha capacidades sem mudar o próprio código | Proposta |
| [0034](0034-central-estacoes-e-instalacao.md) | Central e estações (o Zé na VPS com as funções do PC) e a instalação de um comando | Proposta |
| [0035](0035-agentes-prontos-na-instalacao.md) | Agentes prontos na instalação: Claude Code e Codex nativos, chaves pelo painel | Aceito |
| [0036](0036-contribuicoes-e-atualizacoes.md) | Código aberto: como a comunidade contribui e como o Zé se atualiza | Aceito (atualização em aberto) |
| [0037](0037-integracao-com-sistemas.md) | Integração com sistemas: um método (skill), conectores pelo cérebro e nas sessões, login OAuth | Aceito |
| [0038](0038-fluxos-no-n8n-ze-constroi-e-vigia.md) | Fluxos dos clientes: o n8n executa; o Zé constrói pelo MCP e vigia se cada n8n está de pé | Aceito como direção (plano F1 a F3) |
| [0039](0039-aprovar-sessoes-pela-voz-e-pelo-painel.md) | Aprovar os pedidos das sessões pela voz e pelo painel: o gancho do Claude Code, o primeiro que responde decide | Aceito como direção (E0 feita; E1 a E3) |
| [0040](0040-outros-modelos-pelo-claude-code.md) | Outros modelos (DeepSeek) pelo Claude Code, como conta de provedor; o chat pelo ACP espera | Aceito |
| [0041](0041-vozes-da-nuvem.md) | Vozes da nuvem (ElevenLabs e Fish Audio), opcionais, em streaming, com o Cadu de reserva | Aceito |
| [0042](0042-modo-live-tempo-real.md) | Os três modos (Silencioso, Normal, Live) e o Live em tempo real, com o revezamento do LIGATIA (LiveKit Agents) | Aceito (etapas 1 e 2 feitas; 3 e 4) |
| [0043](0043-ze-se-conhece.md) | O Zé se conhece: o retrato da própria configuração (ferramenta ze_sobre, via rápida e a nota Quem sou), para qualquer modelo | Aceito |
| [0044](0044-pesquisa-na-internet-do-ze.md) | A pesquisa na internet do próprio Zé (internet_pesquisar), sem sessão e com qualquer cérebro, numa consulta à parte | Aceito |
| [0045](0045-ze-se-conhece-inteiro.md) | O Zé se conhece por inteiro: o que sabe fazer (ferramentas, skills, conectores, sessões) e o que fez (a Atividade), em texto e em dados para a tela | Aceito |
| [0046](0046-apresentacoes-da-imersao.md) | As apresentações da Imersão: o Zé vai para o canto e mostra os próprios dados em painéis holográficos que a mão pega | Aceito como direção |
| [0047](0047-cenas-que-o-ze-escreve.md) | Cenas que o Zé escreve: "me explica X" vira gráficos, ondas e 3D na Imersão, de um catálogo de blocos | Em validação |
| [0048](0048-hologramas-3d-montados-com-pecas.md) | Hologramas 3D de verdade, montados com peças, no cartão de modelo que a pinça gira em todos os eixos | Em validação |
