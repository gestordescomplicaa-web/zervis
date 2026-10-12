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
- O ai-memory vem embutido (ADR 0016): o Zé usa o da máquina ou baixa o binário oficial (versão
  e SHA-256 fixos) e o roda junto. As sessões de código do Zé alimentam a memória pelos hooks dele
  e, ao começar, recebem a passagem do que a sessão anterior fez no mesmo projeto.
- Contas dos agentes (ADR 0016): em Modelos, cada agente (Claude, Codex) lista as contas desta
  máquina com o login, o e-mail mascarado e o plano; dá para adicionar outra conta (uma pasta de
  login própria), entrar nela pelo próprio agente (o Zé abre o terminal), escolher a conta em uso
  e remover. O cérebro e as sessões usam a conta escolhida.
- O Codex é motor das sessões de código: ao criar uma sessão, escolhe-se Claude ou Codex; o Codex
  roda pelo `codex exec` na conta da sessão, escreve só na pasta do projeto e continua a mesma
  conversa nos pedidos seguintes. O cabeçalho da sessão mostra o agente e a conta.
- Troca de agente ou de conta no meio da sessão, sem perder a conversa (ADR 0016): na mesma
  agente, a conversa nativa vai para a conta nova e continua inteira; noutro agente, ele recebe a
  passagem do que já foi feito e, ao voltar, retoma a própria conversa com o que mudou. Botão
  Trocar na sessão, ferramenta `sessao_trocar` no cérebro e aviso quando a conta bate o limite.
- Créditos esgotados avisados na tela: quando a conta do agente bate o limite, a sessão mostra
  "Créditos esgotados" com botões "Continuar com <outra conta>", que trocam de conta e mandam de
  novo o pedido que ficou sem resposta. O agente e a conta da sessão se trocam ali mesmo, num
  seletor no cabeçalho.
