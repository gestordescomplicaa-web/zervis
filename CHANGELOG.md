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
- O ícone do Zé (o chimpanzé holográfico) no topo do menu lateral do painel e na aba do navegador;
  acende e pulsa quando o Zé está ativo.
- A sessão de código é o terminal real do agente (ADR 0017): o `claude` ou o `codex` rodando na
  pasta e na conta da sessão, com todos os comandos dele (`/model`, `/effort`, `/compact`...). O
  cabeçalho mantém agente e conta (a troca reabre o terminal sem perder a conversa), o aviso de
  créditos esgotados, os arquivos e os anexos (arrastar, colar ou "+": o caminho vai para o
  terminal). O que se digita e o que o agente responde continuam na conversa do Zé, para a
  passagem entre agentes e para o cérebro acompanhar.
- Trocar de agente não dispara mais um pedido automático: o resumo do que já foi feito entra como
  contexto do agente novo (ou fica no campo, junto com o próximo pedido), sem gastar um turno.
- Modos de fala (ADR 0018): Silencioso (nada falado, chamado desligado), Avisos (padrão: fim de
  sessão em uma frase, aprovação, créditos e erros) e Mãos livres (também a resposta da sessão,
  resumida para ouvir). Troca no menu lateral, na página Voz, com Alt+M ou por voz. O que está
  aberto na tela não é falado.
- Mãos livres de verdade: o Zé sabe de qual sessão se fala (a do último aviso, a aberta na tela
  ou pelo nome), e "diz pra ela rodar os testes" vai para ela; depois de um aviso de sessão ele já
  fica ouvindo a resposta, sem "Ei Zé"; "como está a Loja?" conta os comandos e os arquivos que o
  agente mexeu.
- Voz em qualquer Linux (ADR 0021): a escolha "Escuta" na página Voz, "Sempre" ou "Com a janela
  aberta" (esta só com Hyprland). Sem Hyprland o Zé escuta o chamado enquanto estiver rodando, e
  usa o microfone padrão do sistema quando o MIC FX do Omarchy não existe.
- Voz pelo navegador (plano da voz remota, etapa 1): o botão "Conectar voz" no menu lateral liga o
  microfone do navegador ao Zé por uma sala LiveKit que o próprio Zé baixa, confere e mantém, só
  no endereço local. Conectado, o microfone do PC fecha e a voz do Zé sai pelo navegador.
- Cérebro Codex voltou a subir: o Codex 0.162 recusava o nome do MCP entre aspas no `-c`.
- O chamado repetido ("Ei Zé" de novo, ou o "Eis é" que o Deepgram às vezes escreve) não vira mais
  "Não consegui entender": o Zé segue ouvindo, e o chamado sai do começo do pedido. Pela voz no
  navegador, a fala que começa durante o bip fica no pedido (o navegador já cancela o eco).
- Segurar para falar (ADR 0022): botão no menu lateral e espaço; segurar envia ao soltar, um toque
  começa e outro envia. Nova escolha "Ativação" na página Voz: "Ei Zé" ou Só o botão (no celular,
  o microfone só transmite com o botão apertado). O Silencioso agora só cala o Zé.
- Voz pelo navegador: uma reconexão deixava duas faixas de microfone escrevendo juntas e o Zé
  ouvia frases trocadas; agora vale só a mais recente.
- Voz ao vivo (ADR 0023): com a voz conectada o Zé ouve sem parar, sem "Ei Zé", até desconectar;
  silêncio, "ok" e ruído não encerram nem pedem repetição, e os avisos saem nas pausas. O botão de
  falar virou um pedido só: depois da resposta, o Zé espera o botão de novo.
