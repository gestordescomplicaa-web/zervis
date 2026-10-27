# 0040 — Outros modelos pelo Claude Code, e por que o chat (ACP) espera

- Data: 27/10/2026
- Status: **Aceito** (pedido da pessoa em 27/10/2026: trazer outros modelos, como o DeepSeek,
  sem perder a voz e a aprovação). O chat próprio pelo ACP fica guardado, com a prova abaixo.
- Complementa o [ADR 0016](0016-continuidade-entre-contas-e-agentes.md) (contas dos agentes) e o
  [ADR 0039](0039-aprovar-sessoes-pela-voz-e-pelo-painel.md) (aprovar pela voz e pelo painel).

## Contexto

A voz, o painel e a aprovação das sessões funcionam com o Claude Code e o Codex, cada um com um
adaptador (ganchos, eventos, conectores). Outro agente pediria outro adaptador. A pessoa quer
trazer outros modelos (DeepSeek, Gemini, OpenCode) e perguntou se valeria um agente ou um
terminal próprios, como o Hermes.

## O que foi provado (27/10/2026)

**ACP (Agent Client Protocol)**, com um cliente mínimo em Python e os adaptadores oficiais:

| | Claude (`claude-agent-acp` 0.97) | Codex (`codex-acp` 2.3, Codex 0.164) |
|---|---|---|
| Pedido de aprovação de MCP e resposta | ✅ com nome e argumentos | ✅ sem detalhe no pedido; vem no `tool_call` de antes, pelo `toolCallId` |
| Comando fora da pasta | ✅ pediu, negado, nada criado | bloqueado pela caixa de areia, sem pedir |
| Cancelar com pedido esperando | ✅ | ✅ |
| Reabrir a sessão (`session/load`) | ✅ lembra do que fez | ✅ |

O modo padrão do adaptador do Codex é "Auto review" (uma IA aprova no lugar da pessoa) e aceita
escrever em `/tmp` sem perguntar: quem usar precisa trocar o modo (`session/set_mode`) para
`workspace-write`.

**A regra da Anthropic** ([Legal and compliance](https://code.claude.com/docs/en/legal-and-compliance)):
produto feito com o Agent SDK, que é a base do adaptador ACP do Claude, deve usar chave de API.
Terceiros não podem fazer os pedidos passarem pela assinatura Pro ou Max de quem usa. O que é
permitido é a pessoa entrar com a assinatura dela no Claude Code original, que é o terminal das
sessões do Zé.

**DeepSeek dentro do Claude Code** (API no formato da Anthropic, `ANTHROPIC_BASE_URL`): o terminal
real, com o gancho de aprovação do Zé e um MCP de teste. Funcionaram a aprovação de MCP, a recusa
de um comando fora da pasta e uma tarefa de código com pytest (3 testes passando). Todas as
respostas vieram do `deepseek-v4-pro`.

## Decisão

1. **Outros modelos entram pelo Claude Code**, como uma conta de provedor: a pessoa cola a chave
   em Contas, o Zé testa a chave pedindo a lista de modelos e cria uma conta do Claude Code com
   pasta própria. A sessão leva `ANTHROPIC_BASE_URL`, a chave (`ANTHROPIC_AUTH_TOKEN`) e os
   modelos no ambiente, nunca na linha de comando. Voz, painel, aprovação e conectores ficam
   iguais, sem adaptador novo. O primeiro provedor é a DeepSeek; outro com a mesma API é uma
   entrada em `PROVEDORES`.
2. A conta de provedor vale **só nas sessões**. O cérebro do Zé e o teste do acesso seguem na
   conta do Claude em uso, com os modelos dele. A troca automática por limite não cruza contas,
   porque os modelos não coincidem.
3. **O Claude da assinatura fica no terminal.** O chat próprio pelo ACP fica guardado até valer a
   pena: um terceiro agente de verdade (OpenCode, Antigravity), ou o celular virar o uso principal
   das sessões. A prova acima é o ponto de partida.

## Consequências

- O DeepSeek usa o Claude Code inteiro (ferramentas, compactação, ganchos), com a qualidade do
  modelo dele. No Terminal-Bench 4.0 de outubro de 2026, modelos abertos no Claude Code ficaram
  abaixo do Opus (GLM-5.3 com 41,8% contra 64,8%). A vantagem é o preço.
- A chave fica em `chaves/contas/<conta>`, 0600. Para trocar a chave, remove-se a conta e cola-se
  outra.
- Cada provedor novo precisa ser provado antes de entrar na lista: a API "compatível" de cada um
  aceita partes diferentes do formato da Anthropic.
