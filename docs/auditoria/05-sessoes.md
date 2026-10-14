# Auditoria 5: Sessões

Área 5 do checklist (`docs/checklist.md`). Um passo por vez.

**Conceito.** Uma sessão é um **agente de código** (Claude Code ou Codex) trabalhando numa pasta de
projeto, com a conversa dele, que continua depois de reiniciar. O cérebro do Zé é quem conversa
com você e delega; as sessões programam. Cada sessão escolhe o agente, a conta e o modelo dela.
Até três trabalham ao mesmo tempo. Pode ser numa **cópia isolada** (git worktree): o agente
mexe na cópia, e o projeto só muda quando você aprova.

Já visto no uso (13/10/2026): sessão Claude e Codex, troca de agente no meio com a conversa
passando de um para o outro, pedido por voz a uma sessão, aviso de fim e de aprovação.

## Achados

1. **O modelo da sessão não se escolhe no painel.** A função existe (`ajustar_modelo`), mas nada
   a chama; o cabeçalho só tem agente e conta. **Corrigido em 13/10/2026:** seletor de modelo no cabeçalho, com
   a lista da conta da sessão (com a versão) e "Padrão da conta"; o agente reabre no modelo novo,
   e a conversa continua.
2. **A cópia isolada não tem aprovar nem descartar.** Dá para criar a sessão com "Cópia isolada",
   mas as mudanças ficam presas na cópia: não há como juntá-las ao projeto pelo painel.
   **Corrigido:** prévia, Aplicar e Descartar no painel, com confirmação, bloqueio durante execução
   e preservação de arquivos ignorados. Falha Git impede uma mensagem de sucesso.
   Prova no Chromium com API e projetos temporários; a prova no projeto do usuário continua pendente.

## Passos

### Passo 1. Projeto novo
- **Como:** + → Nome "Teste novo", Projeto novo, pasta `teste-novo`, Claude. Criar; pedir ao
  agente "crie um README dizendo oi".
- **Esperado:** a pasta nasce na raiz de projetos, o agente trabalha nela.
- **Resultado:** ⬜

### Passo 2. Modelo da sessão
- **Como:** no cabeçalho da sessão, escolher o modelo; pedir algo.
- **Esperado:** a sessão passa a usar o modelo escolhido, com a versão no nome.
- **Resultado:** ✅ 14/10/2026. Haiku 4.5 escolhido no cabeçalho; o agente reabriu nele.

### Passo 3. Anexos, Arquivos e Mencionar
- **Como:** anexar uma imagem (+, arrastar ou colar); abrir Arquivos, ver um arquivo, Mencionar.
- **Esperado:** o agente recebe o anexo e o caminho mencionado.
- **Resultado:** ⬜

### Passo 4. Cópia isolada
- **Como:** criar uma sessão com Cópia isolada num projeto com Git; pedir uma mudança; aprovar.
- **Esperado:** o projeto só muda depois de aprovar; descartar joga a mudança fora.
- **Resultado:** ✅ 14/10/2026. "Adiciona NOTAS.md" (f4bf0f1) entrou no projeto ao aplicar; o
  segundo commit (9d1baaa) foi descartado e não está nem na cópia nem no projeto.

### Passo 5. Três trabalhando
- **Como:** pedir trabalho a três sessões e tentar uma quarta.
- **Esperado:** a quarta é recusada com uma mensagem clara (ou espera, se houver fila).
- **Resultado:** ⬜
