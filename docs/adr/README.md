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
| [0049](0049-modelos-3d-prontos-no-acervo.md) | Modelos 3D prontos e livres: o Zé busca, baixa para o Acervo com travas e mostra em holograma | Em validação |
| [0050](0050-mapas-reais.md) | Mapas de verdade: o Zé diz o que mostrar (região, destaques, valores, cidades) e os contornos vêm do IBGE e do Natural Earth, em painel ou em relevo 3D | Em validação |
| [0051](0051-eco-da-voz-remota.md) | O eco da voz remota sai no servidor: o cancelador do WebRTC tira do microfone do celular a fala do Zé na caixa de som | Em validação |
| [0052](0052-objetos-3d-escolhidos-de-olho.md) | Objetos 3D: modelos oficiais da NASA, qualidade em cada achado e o Zé escolhendo pela prévia; a Imersão abre Draco | Em validação |
| [0053](0053-leads-do-whatsapp-pela-voz.md) | Leads do WhatsApp pela voz: o Zé lê a mensagem, lembra até você responder, avisa no celular e responde ditado, com o seu sim | Em validação |
| [0054](0054-whatsapp-do-ze-recepcionista.md) | O WhatsApp do Zé como recepcionista pela voz: a caixa de entrada das conversas privadas, ler, saber quem espera e responder ditado na conversa, com o seu sim | Em validação |
| [0055](0055-lista-de-prioridade-do-whatsapp.md) | A lista de prioridade do WhatsApp: o Zé vigia em tempo real quem você pedir, até você tirar, e escuta a resposta de quem ele respondeu por você | Em validação |
| [0056](0056-arquivo-do-whatsapp.md) | O arquivo do WhatsApp: tudo o que passa pelo WhatsApp (privadas e grupos), para sempre, com busca; leituras sem token e o gasto real na Conversa | Em validação |
| [0057](0057-instagram-so-leitura.md) | O Instagram do Zé, só leitura: perfil e métricas das publicações pela API oficial, analisados pela voz; a página Atendimento vira Redes sociais | Em validação |
| [0058](0058-imagens-reais-na-imersao.md) | Imagens e vídeos reais na Imersão: Wikipédia e Wikimedia Commons com crédito, o print de página atrás de uma trava de rede, e os blocos foto e video nas cenas | Em validação |
| [0059](0059-pesquisa-profunda.md) | Pesquisa profunda: o SearXNG próprio, o leitor de páginas (Trafilatura) atrás da trava de rede, o CNPJ com reserva, o plano B pela pesquisa do Codex e o vigia semanal das fontes de fora | Em validação |
| [0060](0060-pesquisas-guardadas.md) | Pesquisas guardadas: cada pesquisa (a profunda e a resumida) com as fontes, a página Pesquisas do painel e reabrir pela voz sem pesquisar de novo | Em validação |
| [0061](0061-whatsapp-conversa-nova.md) | WhatsApp: começar uma conversa nova pelo número (a empresa que a pesquisa achou), com o sim que confere o nome e o número | Em validação |
| [0062](0062-app-voz-como-ligacao.md) | O app de voz como uma ligação no viva-voz (o cancelamento de eco do Android em qualquer volume) e o eco pelo texto | Em validação |
| [0063](0063-cerebro-local.md) | O cérebro local: um modelo do Ollama (Gemma 4 E4B na GPU integrada) com as ferramentas e a aprovação do Zé, sem gastar os planos | Em validação |
| [0064](0064-barra-de-andamento.md) | A barra de carregamento: o passo (rótulo de cada ferramenta) e o tempo esperado (as medianas reais), na Imersão e no painel | Em validação |
| [0065](0065-propor-melhorias-como-pr.md) | Propor como PR: as melhorias do autodesenvolvimento vão para o GitHub | Em validação |
| [0066](0066-transferir-ligacao-para-o-app.md) | Chamar você durante a ligação e passar para o app de voz, sem derrubar | Em validação |
| [0067](0067-ligar-com-recado.md) | O Zé liga para dar um recado seu, agora ou agendado, e conta como foi | Em validação |
| [0068](0068-supervisor-das-sessoes.md) | O supervisor das sessões (`zervis-oficina`): os terminais dos agentes fora do Zé, e reiniciar o Zé não derruba as sessões | Aceito |
| [0069](0069-fila-duravel-das-automacoes.md) | A fila durável das automações: cada execução gravada com estado e tentativas; ao subir, o lembrete e a pergunta voltam, a ligação vira aviso | Aceito |
| [0070](0070-estado-so-em-sqlite.md) | Estado só em SQLite: avisos, pendências, leads, prioridade e ligações saem do JSON regravado inteiro, com importação única | Aceito |
| [0071](0071-foco-voz-e-oficina.md) | O foco: voz e oficina; Instagram, Imersão, pesquisa, cérebro local, WhatsApp e ligações só recebem correção até a 0.5.0 | Aceito |
| [0072](0072-autodesenvolvimento-so-corrige.md) | O autodesenvolvimento só corrige as falhas do próprio Zé; a fala comum nunca vai para a sessão dele, o pedido é explícito | Aceito |
| [0073](0073-entrada-de-fora.md) | Entrada de fora: depois de ler texto de terceiros (WhatsApp, internet, conectores), nada se executa sem o sim falado | Aceito |
| [0074](0074-sessoes-protegidas.md) | Sessões protegidas: o agente roda no bubblewrap e só enxerga a pasta do projeto | Aceita |
| [0075](0075-segredos-fora-do-agente.md) | Segredos fora do agente: o ambiente sem os segredos do Zé e o `/run/user` escondido | Aceita |
| [0076](0076-ponte-dos-conectores.md) | A ponte dos conectores: o segredo fica com o Zé, o agente leva só a chave da sessão | Aceita |
| [0077](0077-painel-em-modulos-es.md) | O painel em módulos ES: imports explícitos, o estado compartilhado num lugar, sem build | Aceita |
| [0078](0078-abertura.md) | A abertura: música e o resumo do dia, falado, ao abrir o Zérvis | Aceita |
| [0079](0079-ze-como-programa.md) | No PC, o Zé é um programa: abrir liga, fechar a última janela desliga | Aceita |
| [0080](0080-macaco-holografico.md) | O Zé como macaco holográfico: o busto livre preparado no Blender, boca, dentes e expressões | Aceita |
| [0081](0081-cena-no-ritmo-da-voz.md) | A cena no ritmo da voz: cada passo do "explicar" aparece quando o Zé chega à fala dele | Aceita |
| [0082](0082-projetos-3d.md) | Projetos 3D: a peça modelada por uma sessão de código e mostrada como sólido na Imersão | Aceita |
| [0083](0083-imprimir-pela-rede-local.md) | Fatiar e imprimir pela rede local, com o sim de quem usa | Aceita |
| [0084](0084-modo-tv.md) | O Modo TV: uma página leve na TV da casa, aberta pelo navegador dela | Aceita |
| [0085](0085-vigia-da-impressora.md) | O vigia da impressora: erros na hora, impressão mais segura e a câmera | Aceita |
| [0086](0086-app-de-voz-escuta-de-perto-e-imagens.md) | O app de voz: escuta de perto, imagens no celular e uma voz por vez sem briga | Em validação |
| [0087](0087-camera-de-vigia.md) | Câmera de vigia: uma foto local por movimento | Aceita |
