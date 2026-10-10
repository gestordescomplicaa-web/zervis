# Mudanças

## Não lançado

- O Zé começa aqui como projeto aberto, para instalar do zero. Ele herda o núcleo já existente:
  voz (Deepgram e Piper), cérebro trocável, via rápida, memória curta e longa, skills, Foco,
  automações, sessões de agentes de código e o painel.
- Pastas de dados e serviços com o nome `zervis`, fuso do sistema, e nada de nome, caminho ou
  serviço de alguém fixo no código (um teste vigia isso).
- Licença AGPL-3. A voz vem junto: o Piper roda dentro do Zé e a voz Cadu é baixada e conferida
  na primeira subida. Primeiro som em ~150 ms (antes ~320 ms pelo serviço à parte).
- Configuração inicial no painel: sem perfil, o painel abre nela. Perfil (nome, sobre e fuso),
  acesso ao Claude (assinatura ou chave de API, com teste de conexão) e reconhecimento de fala.
  Perfil e acesso também ficam em Ajustes; mudanças valem sem reiniciar (o fuso, no próximo início).
- A chave do Deepgram colada no painel agora liga também a palavra de ativação, sem reiniciar.
- O modo imersivo agora é parte do Zé (ADR 0014): o holograma com as expressões e a boca que
  acompanha a voz, o Núcleo com os orbes e a tela movida pelas mãos vêm no repositório, e o Zé
  sobe o servidor junto com ele. Os testes da página rodam em `make check-imersivo`.
- Modo imersivo limpo para quem começa do zero: as esferas são Mapa, Hoje, Trabalho, Acervo e
  Guia, cada uma alimentada pelo próprio Zé e visível só quando tem conteúdo. Sem Orca nem lista
  de ferramentas no Mapa; medidores técnicos só no modo desenvolvedor (docs/imersivo/ESFERAS.md).
- O Acervo é a pasta do Zé nos dados de quem usa (`acervo/imagens` e `acervo/3d`), sem arquivos de
  exemplo; o orbe só aparece quando há imagem ou modelo 3D nela.
- Guia do modo imersivo em português, sobre o Zé: primeiros passos, gestos, atalhos, as esferas e
  os comandos de voz. Os atalhos de teclado também ficam no menu de configurações (tecla D), e o
  anel mostra o estado em português.
- Modelos em três camadas (ADR 0015): Voz rápida (conversa simples, em menos de um segundo),
  Cérebro (pedidos com ação; agente, com o acesso) e Sessões de código (agentes que continuam
  depois). O Codex aparece como próxima opção do cérebro e das sessões.
- O modo manutenção não depende mais do Orca: o Zé abre uma sessão própria de código no próprio
  repositório ("Zé · manutenção"), a reaproveita nas próximas vezes e fala o resumo do agente. A
  zona protegida, os testes e o reinício seguro continuam iguais.
- Acesso como no Orca: o Zé mostra os agentes instalados nesta máquina (Claude, Codex) e o login
  feito em cada um, sem fazer login de assinatura. Sai o campo de token da assinatura; a chave de
  API da Anthropic fica como alternativa.
- O Orca saiu do núcleo: o cérebro delega trabalho de código às sessões próprias do Zé pelas
  ferramentas `sessoes_listar`, `sessao_criar`, `sessao_enviar`, `sessao_ler` e `sessao_parar`
  (ler é livre; criar, mandar e parar pedem aprovação). Persona e arquitetura acompanham.
