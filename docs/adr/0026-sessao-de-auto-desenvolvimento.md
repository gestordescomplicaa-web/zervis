# 0026 — A sessão de auto-desenvolvimento do Zé, com essência e travas

- Data: 13/10/2026
- Status: **Aceito**; passos 1 e 2 feitos (pedido do usuário: uma sessão única para o Zé se aprimorar,
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

## Consequências
- Para o público: o auto-desenvolvimento precisa de uma cópia git do Zé (a instalação de um
  comando também clona). As melhorias ficam na cópia de cada um; adiante, uma melhoria aprovada
  pode virar um pull request para o projeto, se a pessoa quiser.
