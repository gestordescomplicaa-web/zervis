# 0026 — A sessão de auto-desenvolvimento do Zé, com essência e travas

- Data: 13/10/2026
- Status: **Aceito**; passos 1, 2 e 3 feitos (pedido do usuário: uma sessão única para o Zé se aprimorar,
  com travas para ele não mudar a essência nem virar um "faz qualquer coisa")

## Contexto
O modo manutenção já abria uma sessão de código no repositório do Zé, com zona protegida e
reinício seguro (volta para a versão anterior se a nova não subir). Faltavam: um documento do que o
Zé é; a segurança nova (senha, túnel, atividade, WebSocket) na zona protegida; limite de escopo;
trabalho numa cópia isolada, com aprovar ou descartar no painel; e a ligação com o diagnóstico
(ADR 0025, camada 2).

## Decisão
1. **Essência** (`docs/essencia.md`): voz primeiro, orquestrador de trabalho real, de quem usa,
   aberto; segurança acima da conveniência, tudo registrado, nunca altera o próprio código
   sozinho, linguagem de produto. Nenhuma mudança pode contrariá-la; mudá-la é mudar o projeto.
2. **Zona protegida ampliada:** a essência, a persona e a segurança do acesso e do registro
   (`senha`, `servidor`, `remoto`, `tunel`, `websocket`, `atividade`, o cérebro Codex sem shell).
   Os ajustes que só valem pelo próprio PC passam a morar no módulo de acesso, protegido.
3. **Escopo:** a sessão só trabalha no próprio Zérvis; pedido fora disso ela recusa e indica uma
   sessão comum.
4. **Cópia isolada** (passo 2): a sessão nasce num git worktree (branch `ze/…`); no painel, um
   cartão fixo em Sessões mostra o que mudou e oferece **Aprovar e aplicar** (só com o `make check`
   verde na cópia e, se a zona protegida mudou, a revisão explícita pelo próprio PC) ou
   **Descartar**. Aplicar usa o reinício seguro.
5. **Diagnóstico** (passo 3): o botão Diagnosticar entrega as propostas a essa sessão.
6. **Continuidade entre agentes e contas** (15/10/2026): o autodesenvolvimento tem uma sessão e
   uma cópia ativas. Trocar Claude, Codex ou conta usa o mecanismo das sessões comuns: os fios
   nativos são preservados, o outro agente recebe a passagem e os arquivos continuam na mesma
   branch. O estado da manutenção acompanha a escolha, inclusive ao reabrir a página ou entrar
   por voz. Pedidos pendentes e aprovações continuam associados à sessão. Cópias antigas separadas
   por agente não são removidas automaticamente.
   A troca exige trabalho encerrado; **Interromper** pede confirmação e espera o processo sair,
   preservando a conversa e os arquivos. Limite de uso deixa a sessão em erro, disponível para
   troca. Durante a aplicação de uma atualização, nem a troca nem a interrupção são permitidas.

7. **Sessão central persistente** (15/10/2026): o vínculo entre projeto e sessão fica no banco
   das sessões, independente de agente, conta e modelo. O estado JSON da manutenção é uma
   referência auxiliar. Recuperar a manutenção consulta esse vínculo; uma única cópia legada
   pode ser adotada independente do agente. Várias sem referência exigem escolha explícita;
   registro ou pasta ausentes e cópias órfãs impedem a criação silenciosa de outra sessão.
   A criação e a escolha são serializadas. As rotas antigas de envio, terminal e troca recusam
   sessões substituídas, preservando a consulta ao histórico.
8. **Unificação das cópias legadas:** no próprio PC, o painel mostra as candidatas e oferece
   Unificar sessões, com confirmação. A sessão atual é mantida; só quando não há referência é
   preciso escolher. Nenhuma candidata pode estar trabalhando e a central precisa estar sem
   alterações locais. A migração roda em segundo plano, reservando os comandos dessas sessões.
   Antes de publicar, faz backup privado do banco, preserva fotografias Git das origens em refs
   próprias e verifica a combinação das árvores sem alterar pastas ou índices. Os rascunhos
   versionáveis das origens entram na central; arquivos ignorados continuam nas pastas originais,
   e uma colisão com ignorados da central interrompe a operação. Conflitos deixam todas as cópias
   intactas para resolução na central. As origens e suas branches nunca são apagadas.
   Depois da integração Git, importa mensagens com origem identificada, registra pendências e
   arquiva as referências antigas numa transação. Chaves estáveis permitem retomar uma queda
   depois da integração sem duplicar histórico. O contexto acompanha a próxima abertura/troca,
   inclusive se a conta mudar antes da entrega. Conversas nativas distintas permanecem nas
   origens; a central continua com seus próprios fios nativos e a passagem compartilhada.
   A unificação não aplica código ao Zé em uso: os testes, a revisão da zona protegida e a
   aprovação continuam no fluxo Aplicar. Fallback automático por limite de uso fica para depois.
   Fotografias de rascunhos iguais (árvore e commit de origem) são reutilizadas; uma fotografia
   já reconciliada no histórico da central tem prioridade. Assim uma resolução manual não
   reaparece como conflito só porque uma nova tentativa recebeu outra data de commit. Resolver
   uma cópia antiga preserva as decisões mais recentes: trabalho adiado pode ficar no histórico
   do merge, com essa escolha documentada, sem voltar à versão ativa.

## Consequências
- Para o público: o auto-desenvolvimento precisa de uma cópia git do Zé (a instalação de um
  comando também clona). As melhorias ficam na cópia de cada um; adiante, uma melhoria aprovada
  pode virar um pull request para o projeto, se a pessoa quiser.
- A sessão do Zé não fica junto dos projetos: mora na página **Melhorias** (grupo O Zé), só no
  próprio PC, com o Diagnosticar no topo (pedido do usuário, 13/10/2026).
