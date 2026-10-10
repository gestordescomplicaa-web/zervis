# 0016 — Continuidade entre contas e agentes, com o ai-memory embutido

- Data: 10/10/2026
- Status: **Aceito** (pedido do usuário: "continuar de outra sessão do Codex ou do Claude, o mesmo
  projeto, selecionando as contas"; o ai-memory embutido no Zé)

## Contexto
No Orca, cada conta do Codex é uma pasta (`CODEX_HOME`) e trocar de conta no meio de uma sessão
não continua: a sessão nativa fica na pasta da conta antiga e o caminho é recomeçar. O ai-memory
(akitaonrails/ai-memory, MIT) resolve a troca de agente com um "workstream": cada agente mantém a
sua sessão nativa e um registro portátil da parte visível leva ao próximo só o que mudou.

## Testes (10/10/2026, Codex 0.160.1, Claude Code 2.1.291)
| Teste | Resultado |
|---|---|
| Claude: criar sessão e retomar (`claude -p --resume`) | lembrou a palavra secreta |
| Codex: criar sessão e retomar (`codex exec resume`) | lembrou |
| Codex: copiar a sessão (`sessions/AAAA/MM/DD/rollout-*.jsonl`) para outra `CODEX_HOME`, mesma conta | retomou |
| Codex: sessão criada na conta Plus, com raciocínio criptografado, retomada na conta gratuita | **retomou e lembrou**; só avisou da troca de modelo (o plano gratuito usa outro) |
| Codex: entrar numa segunda conta derrubou a primeira? | não |
| Claude: copiar a sessão (`projects/<pasta>/<id>.jsonl`) para outro `CLAUDE_CONFIG_DIR` | retomou (uma conta só disponível; o mecanismo é o mesmo) |

## Decisão
1. **Conta = pasta de login do próprio agente** (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`), criada pelo
   Zé e com o login feito pela pessoa no agente. A pasta padrão (`~/.claude`, `~/.codex`) é a
   primeira conta.
2. **Trocar de conta no mesmo agente** copia a sessão nativa para a pasta da conta nova e retoma
   com o resume do próprio agente: continuidade completa, sem resumo.
3. **Trocar de agente** retoma a sessão nativa daquele agente nesse trabalho, se houver, e entrega
   o que aconteceu desde a última vez dele (o registro da sessão no Zé e o estado do git); sem
   sessão anterior, começa com o resumo e as mensagens recentes. Mesmo padrão do ai-memory.
4. **O ai-memory vem embutido:** o Zé baixa o binário oficial fixado por versão e SHA-256 (como a
   voz) e o roda como serviço filho; as sessões do Zé alimentam o ai-memory e ganham a busca dele.
   Se a máquina já tiver o ai-memory rodando, o Zé usa esse.
5. A troca automática ao bater o limite fica desligada por padrão: trocar entre contas próprias é
   escolha de quem usa, dentro dos termos de cada empresa.
