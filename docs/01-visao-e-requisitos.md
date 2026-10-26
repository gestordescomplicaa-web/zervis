# 01 — Visão e requisitos

Data: 06/10/2026, revisada em 26/10/2026 (o painel no lugar do Barehands, as sessões próprias no
lugar do Orca e o atendimento no WhatsApp). Fonte: conversas com o usuário na sessão de
desenvolvimento do Zé.

## Visão

Um Zé que é um **sistema desta máquina**, não um app: ele lê e opera o computador, e os
outros sistemas se adaptam a ele. O usuário o usa de fone, sem olhar para a tela: ele fala "Ei Zé",
pede, ouve a resposta e é avisado do que importa. Com o tempo o Zé lembra
das preferências, aprende procedimentos (skills) e cuida de rotinas sozinho
(automações). A interface visual é o painel, com o modo imersivo numa aba (ADR 0014); o código é
feito nas sessões do próprio Zé, com o Claude Code e o Codex (ADR 0015).

## Requisitos funcionais

### R1 — Liga/desliga pelo rosto
- R1.1 Há um rosto conectado (a janela do Zé aberta, a escuta sempre ligada **ou** o celular
  conectado pela voz remota; ADR 0021) ⇒
  Zé **ativo**: escuta "Ei Zé", responde, avisa — pelo rosto conectado.
- R1.2 Nenhum rosto conectado ⇒ Zé **inativo**: microfones fechados, nenhuma fala, nenhum card.
  Automações agendadas continuam rodando, mas guardam o resultado em vez de falar.
- R1.3 Ao reativar, no máximo **um** resumo falado do que ficou pendente (nunca a fila inteira).
- R1.4 O estado ativo/inativo é visível no próprio anel (cor/forma) e consultável por voz.

### R2 — Conversa por voz
- R2.1 Palavra de ativação dedicada (detector pessoal "Ei Zé" já treinado).
- R2.2 Resposta falada em português do Brasil natural (normalizador de fala).
- R2.3 Primeira fala em até ~1 s depois que o cérebro começa a responder (streaming por frase).
- R2.4 Interromper a fala dizendo "Ei Zé".
- R2.5 Comandos de console por frase exata (ex.: "silenciar avisos", "parar de escutar").

### R3 — Cérebro trocável
- R3.1 Claude e Codex como provedores iniciais, **por login de assinatura** (como o usuário já usa). A chave de API da Anthropic colada no painel também vale; se ela for recusada, o fundo segue pela assinatura.
- R3.1a OmniRoute local (`127.0.0.1:20128`) como terceiro provedor, para usar as rotas que o usuário monta nele ([ADR 0008](adr/0008-omniroute-como-provedor-do-cerebro.md)).
- R3.2 Uma interface interna única (`Brain`) — o resto do sistema não sabe qual provedor está ativo.
- R3.3 Troca de provedor por configuração e por voz ("usar o Codex").
- R3.4 Persona e regras de fala vêm de arquivos do Zé, não do provedor.

### R4 — Memória
- R4.1 Memória curta e curada sempre carregada (perfil do usuário + fatos do ambiente).
- R4.2 Busca no histórico de conversas antigas quando a pergunta for sobre o passado.
- R4.3 Escritas de memória feitas pelo próprio Zé ficam **pendentes** até o usuário aprovar
  (por voz ou no front), com opção de liberar categorias seguras depois.
- R4.4 Proteção contra injeção: nada vindo de sessões, web ou mensagens vira memória sem revisão.

### R5 — Skills que melhoram
- R5.1 Skills no formato `SKILL.md` (padrão agentskills.io, o mesmo de Hermes, Claude e Codex).
- R5.2 Carregamento progressivo: só nome e descrição sempre; o conteúdo quando necessário.
- R5.3 Revisão em segundo plano propõe criar ou corrigir skills depois de conversas relevantes.
- R5.4 Toda proposta vira pendência com diff; só vale depois de aprovada.
- R5.5 Curadoria: skills sem uso ficam "paradas" e depois arquivadas (nunca apagadas).

### R6 — Automações e avisos
- R6.1 Tarefas agendadas (uma vez, intervalo, cron, data exata), com ou sem cérebro (script puro).
- R6.2 Fontes de eventos: agenda, sessões de código delegadas pelo Zé, pedidos de aprovação,
  falhas, o vigia do n8n.
- R6.3 Fila durável de avisos com prioridade, sem repetição e com expiração (já existe no Zé atual).
- R6.4 Um aviso só é falado se o Zé estiver ativo; senão vira pendência.

### R7 — A oficina (sessões de código próprias)
- R7.1 O Zé delega trabalho de código às próprias sessões: o Claude Code ou o Codex numa pasta de
  projeto, com as skills e os conectores daquele projeto (ADR 0015 e 0037). Era o Orca até 10/10.
- R7.2 Recebe o resultado (terminou, falhou ou precisa de você) e avisa por voz.
- R7.3 Pedidos de permissão: descrição falada + aprovação por voz com confirmação (já existe).
- R7.4 Sessões abertas manualmente pelo usuário **não** são narradas; só pedidos de aprovação e falhas delas.

### R9 — Celular Android (mãos livres longe do PC) — última fase
- R9.1 Fone no celular, Zé no PC: mesma conversa, mesmos comandos, mesmos avisos.
- R9.2 Funciona em casa (Wi-Fi) e fora (rede móvel), sem expor o PC na internet aberta.
- R9.3 Caso central: tocar as sessões de código por voz — perguntar estado, delegar, aprovar, ouvir
  "terminou/falhou/precisa de você".
- R9.4 Funcionar com a tela do celular bloqueada (a confirmar na Prova 4).
- R9.5 No modo remoto o microfone e os alto-falantes do PC ficam desligados.

### R8 — A máquina (Omarchy 4)
- R8.1 Ler o estado do computador: recursos, bateria, rede, áudio, janelas, agenda, atualizações.
- R8.2 Operar o computador por voz: volume, brilho, abrir e focar apps, notificações, tema, capturas.
- R8.3 Receber eventos do sistema (bateria fraca, atualização, tema, janelas) sem *polling*.
- R8.4 Catálogo de ações gerado dos metadados dos comandos `omarchy-*`, atualizado sozinho.
- R8.5 Política de risco por nível (leitura livre → proibido), detalhada em [07](07-sistema-omarchy.md).
- R8.6 Nunca simular teclado para agir; preferir comandos e IPC.

## Requisitos não funcionais

- **Desempenho:** núcleo ocioso < 5% de CPU; o custo maior deve ser o modo imersivo (câmera).
- **Confiabilidade:** reinício do processo não perde avisos, pendências nem agendamentos.
- **Segurança:** segredos só em arquivos 0600 ou chaveiro; nunca em logs, memória ou skills.
- **Privacidade:** áudio só é transcrito depois da palavra de ativação; nada sai da máquina além
  das chamadas ao provedor do cérebro.
- **Operação:** serviço systemd de usuário; um único comando de status mostra tudo.
- **Ambiente:** Omarchy 4 (Arch, Hyprland), Ryzen 5 8500G, 30 GB RAM, Radeon 740M com 512 MB.

## Fora do escopo agora

- Ligação telefônica comum (SIP); o celular entra pelo app, não por chamada.
- Plataformas de mensagem (Telegram, WhatsApp etc.) como canal de conversa **com você**. Atender
  os seus clientes no WhatsApp é outra coisa e entrou depois, na Central de Atendimento (ADR 0031).
  O coletor de
  WhatsApp do Hermes segue separado, a serviço do projeto JEV. Exceção (14/10/2026): o Zé lê as
  notificações do WhatsApp deste computador (quem mandou e o começo da mensagem), um modelo sem
  ferramentas julga se é um lead quente (quer comprar ou mostra interesse real: preço, pagamento,
  proposta, orçamento, quer fechar) e, se for, ele avisa com uma frase fixa ("Lead quente no
  WhatsApp: Ana."), no máximo uma vez por contato a cada 15 minutos. Desligado por padrão (Voz >
  WhatsApp, ou "liga os avisos do WhatsApp"). O trecho da mensagem vai ao modelo das respostas
  rápidas (ou ao Claude da assinatura) só para o julgamento; não vira fala, não entra na conversa
  do cérebro e não é registrado. O Zé nunca responde nem abre a conversa. Requer o `busctl`
  (systemd).
- Uso por mais de uma pessoa.
- Modelos locais como cérebro principal (podem entrar depois como provedor extra).
