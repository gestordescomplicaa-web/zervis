# Mudanças

## Não lançado

- Memória: o que muda no meio da conversa (painel, aprovação, voz) vale já no próximo pedido.
- Memória: as sugestões que o Zé aprende numa conversa aparecem no painel, com Aprovar e Descartar.
- OmniRoute no painel: Cérebro → OmniRoute, com o endereço e a chave do OmniRoute de quem usa
  (local por http ou num servidor por https) e a lista de modelos dele; também nas Respostas rápidas.
- Respostas rápidas: o modelo vem da lista com a versão (Claude, Codex, Anthropic); o Codex do
  cérebro mostra "Padrão da conta" quando não há modelo escolhido.
- Modelos: o modelo do cérebro se escolhe no painel (a mesma lista das sessões) e vale na hora;
  "Voz rápida" passa a se chamar "Respostas rápidas" e fica junto do Cérebro.
- O modo de fala "Avisos" passa a se chamar "Normal" ("modo avisos" por voz continua valendo).
- Chamado universal: o "Ei Zé" vem treinado no repositório, com vozes sintéticas, e funciona para
  qualquer pessoa sem gravar a própria voz. A gravação pessoal virou ajuste opcional.
- O chamado ignora silêncio e som de fundo: precisa de volume de alguém falando ao microfone
  (configurável em `ativacao.nivel_minimo_dbfs`).
- Silencioso trava o microfone: nem "Ei Zé", nem o botão, nem o Ao vivo; a conversa é pela tela.
- O Zé tem a vez: enquanto ouve, pensa ou fala, vídeo e música (navegador e players) pausam e
  voltam depois. Chamado sem ninguém falar depois fecha a escuta em 6 s.
- "Repete" (ou "não entendi", "fala de novo") repete a última fala do Zé inteira, na hora.
- Central de avisos (ADR 0029): o Zé narra as sessões em vez de ler a resposta delas ("A sessão
  Loja terminou. Ela corrigiu o login."), com um toque antes; aprovação e falha passam na frente;
  vários avisos viram uma oferta ("Duas novidades… Começo pela Site?") e a pessoa conduz com
  "começa", "próximo", "depois" e "o que ela disse?". A Conversa mostra o que espera.
- Conversa no painel: o fio do dia com o Zé (pedidos, respostas e avisos) e o campo para escrever.
  No Silencioso, o que o Zé não falou aparece também como notificação em qualquer página.
  Conectores passa a carregar só quando aberto.
- Revisão do painel: as sessões no terminal (Claude e Codex) passam a receber as skills do
  usuário, como a página promete. Reiniciar o Zé não registra mais "o túnel caiu" nem erros de
  conexão do painel; o diagnóstico ignora o encerramento normal do agente.
- Segurança: aplicar ou reiniciar o Zé só do próprio PC. A voz do celular e o texto digitado não
  aplicam, e a zona protegida nunca entra pela voz, só pelo painel com a revisão marcada.
- Manutenção é um estado do Zé (ADR 0028): liga por voz ou no Autodesenvolvimento, deixa o
  painel em laranja, e só nele valem Diagnosticar e Aplicar. Aplicar espera as sessões de outros
  projetos terminarem, sem interromper ninguém.
- Reinício e atualização: o painel mostra "Reconectando…" e recarrega sozinho quando o Zé volta.
  A volta automática desiste em segundos quando a versão nova cai ao subir, e a cópia isolada
  volta a ficar igual ao Zé em uso. Volta testada de ponta a ponta (13/10/2026).
- A página Melhorias passa a se chamar Autodesenvolvimento, assim como a sessão do Zé.
- Imersão no PC só roda à vista: sair dela ou esconder o painel desliga a câmera e o holograma.
- Diagnóstico de uso: o túnel do acesso de fora sobe de novo sozinho quando cai e revoga o
  endereço antigo; a voz do navegador reconecta após queda de rede e separa "desligou" de "caiu";
  o modo imersivo guarda a própria saída e o vigia mostra o código de saída, sem chamar de queda
  a saída ordenada; escuta vazia fecha com o bip em vez de "não entendi"; o relatório agrupa cada
  erro não tratado pela exceção final e onde ela nasceu.
- Regras de fala (ADR 0027): aviso falado em no máximo 30 palavras, com o resto na tela; o fim
  da sessão de melhorias é uma frase; aviso cortado volta uma vez só; o mesmo aviso não se repete
  em 2 minutos.
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
- Menu lateral com grupos recolhíveis (Trabalho, O Zé, Ajustes), lembrados no navegador; o grupo
  da página aberta fica sempre aberto. A voz virou uma barra no rodapé do menu: modo de fala, Ao
  vivo e Falar. No celular, o menu vira uma barra no topo e o conteúdo não fica mais por baixo.
- O ícone do Zérvis no menu mostra o estado do Zé com animação: ondas ouvindo, brilho girando na
  borda pensando, pulso falando, âmbar esperando o "sim"; apagado quando inativo. O texto do estado
  saiu do menu (fica na dica do ícone), e o painel confere o estado a cada segundo.
- Acesso pelo celular (plano da voz remota, etapa 2): na página Voz, Ativar publica o painel e a
  sala de voz na rede privada do Tailscale (`tailscale serve`, HTTPS válido), e a mídia da voz passa
  a usar o endereço da máquina nessa rede. Nada fica aberto na internet.
- Voz pelo celular em casa: o Chrome do Android não manda o áudio pela VPN do Tailscale; o servidor
  de voz passa a oferecer também o endereço do PC na rede de casa, e o cartão "Acesso pelo celular"
  mostra o comando que libera o firewall só para essa rede. O registro do LiveKit fica em
  `livekit.log`, na pasta de estado.
- Senha de acesso (roteiro, passo 4.1): o próprio PC entra direto; qualquer outro aparelho passa
  pela tela Entrar, uma vez por aparelho ("lembrar este aparelho": 30 dias). A senha é guardada só
  como resumo (scrypt), cinco erros bloqueiam por 15 minutos, e trocar a senha ou "Encerrar
  acessos" desconecta todos. Ativar o acesso pelo celular exige a senha definida.
- Voz pelo HTTPS (ADR 0024): o Ao vivo do navegador manda o microfone e recebe a voz do Zé pelo
  WebSocket do próprio painel, sem WebRTC: onde o painel abre, a voz funciona, sem porta nem firewall.
  A tela fica ligada durante o ao vivo. O painel não carrega mais o cliente do LiveKit.
- Acesso de qualquer lugar sem nada no celular (roteiro, passo 4.3): em Voz > Acesso pelo celular,
  Ativar abre um túnel do Cloudflare que o Zé baixa e confere, e mostra o endereço e um QR; o
  celular abre no navegador, entra com a senha e fala pelo ao vivo, em casa ou no 4G. O painel vira
  app instalável (ícone na tela inicial). Pedido que chega por túnel ou proxy nunca vale como o
  próprio PC. O Tailscale fica como alternativa, só se estiver instalado.
- Segurança do acesso de fora: código do autenticador (verificação em duas etapas, TOTP) obrigatório
  para o acesso de qualquer lugar; bloqueio de tentativas por endereço de origem (quem ataca não
  tranca quem usa); aviso falado e na tela quando um aparelho entra, com a lista de aparelhos e
  Desconectar em cada um; ajustes de acesso (senha, código, túnel) só pelo próprio PC.
- Imersão no celular: em outro aparelho, a aba Imersão mostra o holograma do Zé em tela cheia,
  reagindo à conversa (ondas ouvindo, que crescem com a sua voz; brilho girando pensando; pulso no
  volume real da fala; âmbar esperando o "sim"), com Ao vivo e Falar grandes embaixo. A Imersão
  completa, com as mãos e o Núcleo, continua só no PC.
- Painel no celular refeito: barra no topo com o menu, menu deslizante com os grupos e a voz numa barra
  fixa embaixo (Fala, Ao vivo, Falar); em Sessões, uma coisa por vez (a lista ou a sessão, com
  "Sessões" para voltar) e o cabeçalho da sessão em duas linhas. Holograma em resolução cheia.
- Depois de reiniciar o computador, o Zé dizia que o Codex não estava instalado: o serviço sobe com
  um PATH mínimo, antes de a sessão carregar o ambiente da pessoa. Agora o Zé completa o PATH na
  subida com o do shell de login e as pastas pessoais de programas (~/.local/bin, mise, npm, bun…).
- Atividade (ADR 0025): tudo o que o Zé executa fica registrado, com o comando, como foi autorizado
  (livre, aprovado, frase exata), de onde veio o pedido e o resultado; também as negadas, as falhas,
  o que ele não entendeu (com o que ouviu), as correções e os pedidos atendidos. Nova página
  Atividade, com o registro técnico do serviço e "Copiar diagnóstico". Nova ação: suspender o
  computador (confirmação falada).
- Essência do Zé (`docs/essencia.md`, ADR 0026): o que ele é e não deixa de ser. A sessão de
  manutenção passa a ler a essência, só trabalha no próprio Zé (recusa o resto) e tem a zona
  protegida ampliada com a segurança nova (senha, túnel, atividade, WebSocket) e a persona.
- Sessão "Zé · melhorias" (ADR 0026, passo 2): fixa no topo de Sessões, trabalha numa cópia isolada
  do Zé (git worktree) e mostra o que mudou; "Aprovar e aplicar" roda os testes na cópia, junta ao
  Zé em uso e reinicia com o reinício seguro (zona protegida exige a revisão marcada; só pelo
  próprio PC); "Descartar" volta a cópia ao Zé em uso. "Reinicia o Zé" por voz também aplica.
- Página Melhorias (ADR 0025 e 0026): a sessão do Zé sai de Sessões e mora aqui, só no próprio PC.
  Diagnosticar monta o relatório do que deu errado (falhas, não entendi, correções, negadas e os
  erros que mais se repetem no registro técnico, agrupados por causa) e o entrega à sessão, que
  propõe as correções sem implementar até a pessoa escolher.
- Sessão de código aberta e fechada sem nenhum pedido não trava mais ao reabrir ("No conversation
  found"): o Zé só retoma conversas do Claude que existem e, se não existir, começa uma nova.
