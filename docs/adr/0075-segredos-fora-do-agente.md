# 0075 — Segredos fora do agente: o ambiente sem os segredos do Zé

- Data: 10/11/2026
- Status: **Aceita** (testado no `make check` e com o `claude` e o `codex` desta máquina,
  logados, dentro do isolamento e com o ambiente filtrado).

## Contexto

O Zé abria cada agente com o próprio ambiente inteiro. Esse ambiente vem do perfil de quem usa,
que costuma exportar tokens de outros serviços: em 10/11/2026, um token do n8n chegava a todas as
sessões, protegidas ou não. Um `env` do agente punha o token no contexto enviado ao modelo.

Na sessão protegida (ADR 0074) sobrava ainda o `/run/user/<uid>`: lá moram o D-Bus (o chaveiro,
e o `systemd-run --user`, que roda um comando fora do isolamento), o ssh-agent e o gpg-agent.

É o começo do item "cofre de segredos fora do agente" da Frente 2 do
[plano de maturidade](../plano-maturidade.md): "nenhum segredo no contexto enviado ao modelo".

## Decisão

1. **O agente recebe o ambiente sem as variáveis de segredo** (`agentes.sem_segredos`): sai o que
   tem nome de segredo (`*_TOKEN`, `*_KEY`, `*_API_KEY`, `*_SECRET`, `*_PASSWORD`, `*_AUTH*`,
   `*CREDENTIALS*`, …). Ficam:
   - o login do próprio agente: `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` e
     `CLAUDE_CODE_OAUTH_TOKEN` para o Claude; `OPENAI_API_KEY` e `CODEX_API_KEY` para o Codex
     (um não recebe o do outro). Com `CLAUDE_CODE_USE_BEDROCK` ou `CLAUDE_CODE_USE_VERTEX`, as
     credenciais da nuvem (`AWS_*`, `GOOGLE_*`);
   - o que a sessão entrega de propósito: a conta, os segredos dos conectores marcados para o
     projeto (ADR 0037) e a chave do gancho de permissão;
   - o `SSH_AUTH_SOCK`, que é um endereço (na sessão protegida ele não leva a nada).
2. **Vale para os três caminhos:** o terminal (o supervisor e o terminal local deixam de juntar o
   ambiente do Zé por baixo), o `codex exec` e o SDK do Claude (que junta o ambiente do Zé por
   conta própria: os segredos vão vazios).
3. **Na sessão protegida, o `/run/user/<uid>` vira uma pasta vazia.**

## Consequências

- Um agente que dependia de um token do perfil (um `GITHUB_TOKEN` para o `gh`, por exemplo) deixa
  de recebê-lo. O caminho certo é o conector do projeto, que entrega só àquele projeto.
- A memória longa continua: o ai-memory fala com o servidor dele por `127.0.0.1`. Esse servidor
  não pede autenticação, então o agente ainda consegue buscar o histórico de todos os projetos;
  fechar isso é ligar a autenticação do ai-memory com uma chave só de leitura do projeto.
- Os segredos dos conectores saíram do agente no [ADR 0076](0076-ponte-dos-conectores.md) (a
  ponte dos conectores).
