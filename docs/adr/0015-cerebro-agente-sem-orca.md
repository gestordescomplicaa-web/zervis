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
1. **O cérebro do Zé é um agente escolhido por quem usa:** Claude Code (Agent SDK, assinatura ou
   chave) ou Codex (assinatura do ChatGPT ou chave da OpenAI). O mesmo motor serve às sessões de
   código. A escolha fica no painel.
2. **A conversa é do Zé, não do agente.** A sequência (memória curta, últimos turnos da conversa
   atual, Foco, perfil) é montada pelo Zé e entregue a qualquer cérebro. Trocar de cérebro no meio
   continua a conversa de onde parou.
3. **O ai-memory é a memória longa comum aos dois:** indexa as sessões dos dois agentes, e o Zé
   busca nele qualquer que seja o cérebro do momento (opcional; sem ele, o Zé funciona sem memória
   longa).
4. **O Orca sai do núcleo.** A delegação de código passa para as sessões próprias; o modo
   manutenção (o Zé se aperfeiçoando a pedido de quem usa) vira uma sessão própria aberta no
   repositório do Zé, com o motor escolhido.

## Consequências
- Ordem de trabalho em `docs/roteiro.md`: modo manutenção sobre as sessões próprias; saída do
  Orca (ferramentas, persona, monitor); motor Codex no cérebro e nas sessões; continuidade da
  conversa na troca de cérebro.
- O OmniRoute fica como opção avançada ("Ponte"), não como caminho padrão.
