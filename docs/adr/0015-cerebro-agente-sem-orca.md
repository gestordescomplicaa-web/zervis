# 0015 — O cérebro é um agente (Claude Code ou Codex), sem o Orca

- Data: 10/10/2026
- Status: **Aceito** (decisão do usuário: "posso escolher Claude Code ou Codex como cérebro, e o
  ai-memory persiste nos dois: independente do que eu use, continua a mesma lógica e sequência
  da sessão")
- Substitui o papel do Orca na ADR 0006 (Orca como oficina) e na ADR 0007

## Contexto
O Zé antigo delegava código ao Orca e abria o modo manutenção numa sessão do Orca. Isso servia a
uma máquina, não a quem instala do zero. O Zé novo já tem sessões próprias de agentes de código
(`jarvis/oficina/sessoes.py`, pelo Agent SDK) e já lê o histórico do ai-memory, que guarda as
sessões do Claude e do Codex.

## Decisão
O Zé usa modelos em **três camadas**, cada uma escolhida pelo que pede:

| Camada | Para quê | Pede do modelo | Motor |
|---|---|---|---|
| **Voz rápida** | Conversa simples, resposta em menos de 1 s | Latência e custo baixos, contexto curto, sem ferramentas pesadas | Um modelo rápido por chave de API (ou o Claude pela assinatura) |
| **Cérebro** | Pedidos com ação: decidir, usar as ferramentas do Zé, abrir sessões | Ferramentas e raciocínio; alguns segundos | Um agente: Claude Code ou Codex |
| **Sessões de código** | Trabalho longo num projeto, que continua depois | Agente completo, sessão persistente, segundo plano | Um agente: Claude Code ou Codex |

1. **O cérebro e as sessões são agentes escolhidos por quem usa:** Claude Code (Agent SDK,
   assinatura ou chave) ou Codex (assinatura do ChatGPT ou chave da OpenAI). A voz rápida é uma
   escolha à parte, por latência. Tudo fica na página Modelos do painel, um cartão por camada.
2. **A conversa é do Zé, não do modelo.** A sequência (memória curta, últimos turnos, Foco,
   perfil) é montada pelo Zé e entregue a qualquer camada. Trocar o modelo de qualquer camada
   não quebra a conversa.
3. **O ai-memory é a memória longa comum:** indexa as sessões dos dois agentes, e o Zé busca nele
   qualquer que seja o modelo do momento (opcional; sem ele, o Zé funciona sem memória longa).
4. **O Orca sai do núcleo.** A delegação de código passa para as sessões próprias; o modo
   manutenção (o Zé se aperfeiçoando a pedido de quem usa) vira uma sessão própria aberta no
   repositório do Zé, com o motor escolhido.

## Consequências
- Ordem de trabalho em `docs/roteiro.md`: a página Modelos em três cartões; modo manutenção sobre as sessões próprias; saída do
  Orca (ferramentas, persona, monitor); motor Codex no cérebro e nas sessões; continuidade da
  conversa na troca de cérebro.
- O OmniRoute fica como opção avançada ("Ponte"), não como caminho padrão.
