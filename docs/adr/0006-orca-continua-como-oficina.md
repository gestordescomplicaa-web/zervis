# 0006 — O Orca continua como oficina (executor de código)

- Data: 06/10/2026
- Status: **Aceito** (o usuário: "vamos continuar com o Orca")

## Contexto
O usuário avaliou trocar o Orca por OpenCode, Goose, OpenHands, Codex app-server ou Cline CLI,
pensando em algo mais acessível para o JARVIS controlar.

## Ponto decisivo: login de assinatura
O usuário usa Claude e Codex **por assinatura**, não por chave de API.
- A Anthropic **não permite** que ferramentas de terceiros ofereçam o login do Claude.ai nem usem os
  limites da assinatura; elas devem usar chave de API (termos de autenticação e política de OAuth,
  formalizados em fevereiro de 2026; o bloqueio técnico começou em janeiro). Na prática, OpenCode,
  Goose, OpenHands e Cline usam o Claude **só com chave de API**.
- O Claude Code (o CLI oficial) usa a assinatura normalmente — e é ele que roda dentro do Orca.
- O login do ChatGPT/Codex funciona em mais ferramentas (o OpenCode, por exemplo, aceita).

## Análise das opções

| Opção | Camada | Claude por assinatura | Veredito |
|---|---|---|---|
| **Orca** | Oficina: worktrees, terminais, várias sessões visíveis, orquestração, CLI JSON | Sim (roda o Claude Code oficial) | **Manter** |
| OpenCode | Agente de código (um executor) | Não (só API) | Pode rodar **dentro** do Orca (`worker-start --agent opencode`) se um dia fizer sentido |
| Goose | Agente pessoal completo + executor | Não (só API) | Concorre com o próprio JARVIS; não é peça dele |
| OpenHands | Plataforma de agentes (Docker, servidor) | Não (só API) | Pesado demais para o "leve e diário" |
| Codex app-server | Motor do Codex sem tela (JSON-RPC) | Sim (login do ChatGPT) | **Usar como o cérebro Codex do JARVIS** (Prova 2), não como oficina |
| Cline CLI | Agente de código sem tela | Não (só API) | Abaixo dos demais |

A comparação recebida mistura camadas: quase todas as alternativas são **agentes**, e o Orca é a
**oficina que hospeda agentes** (inclusive OpenCode, Cursor, opencode e outros).

## Decisão
1. O Orca continua sendo a oficina: o usuário enxerga as sessões, os worktrees e o progresso, e o
   JARVIS controla pela CLI e pela orquestração nativa.
2. No JARVIS, a oficina fica atrás de uma interface (`Oficina`), com o Orca como primeira
   implementação. Trocar no futuro custa uma implementação nova, não um redesenho.
3. O Codex app-server entra como candidato forte para o `CodexBrain` (cérebro), na Prova 2.

## Consequências
- Nada muda no roadmap (Fase 3 = Oficina com o Orca).
- Revisar se a Anthropic mudar a política ou se o Orca deixar de atender (custo, estabilidade).
