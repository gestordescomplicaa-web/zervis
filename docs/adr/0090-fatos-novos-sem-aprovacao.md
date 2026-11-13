# 0090 — Fato novo na memória entra sem pedir; trocar, tirar e skill continuam pedindo

- Data: 13/11/2026
- Status: **Em validação**: medir em duas semanas quantos fatos gravados sozinhos foram removidos.

## Contexto

A revisão em segundo plano (ADR 0011) segue os critérios do Hermes, mas no Zé toda sugestão
esperava a aprovação. De 13/10 a 13/11/2026: 6 sugestões aprovadas, 16 descartadas (15 numa
limpeza só, em 03/11) e 4 paradas desde 12/11. A memória do usuário ficou em 409 de 2.000
caracteres. No mesmo período, o Hermes desta máquina (perfil `meugerente`) encheu o `USER.md` a
95% e fez 24 mudanças de skill, porque grava sozinho o que é novo e só pede aprovação para trocar
ou apagar (investigação de 13/11/2026 na pasta do REA, `hermes-memoria/README.md`).

## Decisão

1. **Fato novo na memória** ("usuario" ou "jarvis") que a revisão propõe é gravado sem pedir,
   depois das mesmas checagens da escrita normal: varredura de injeção e de segredos, duplicata e
   limite de tamanho. Se a memória encheu entre a revisão e a gravação, ele volta a ser sugestão.
2. **Continuam pedindo aprovação:** trocar ou tirar uma entrada, criar ou corrigir skill, e
   qualquer escrita pedida pelo cérebro durante a conversa.
3. **Sem fala:** o Zé não anuncia o que gravou sozinho. O diário registra ("Aprendido sozinho") e
   a página Memória marca a entrada com "Aprendido"; o "×" de sempre remove.
4. **Fatos, não ordens:** o prompt da revisão pede o fato ("prefere respostas curtas"), nunca a
   ordem ("responda curto"), como o Hermes: uma ordem relida noutra conversa passa por cima do
   pedido da hora. Com a gravação sem aprovação, isso passa a ser a principal proteção.
5. **Desligável:** `revisao.gravar_fatos_novos = false` volta ao comportamento antigo.

## Consequências

- O aprendizado deixa de depender de a pessoa lembrar de aprovar. As 4 sugestões antigas
  continuam esperando a decisão.
- A medida: o diário registra "Aprendizado removido" quando a pessoa tira pelo painel um fato que
  entrou sozinho. Se em duas semanas a maior parte for removida, o problema é a qualidade da
  revisão (modelo menor, só a conversa), e o caminho é o do ADR 0011: revisar com o modelo
  principal.
- Uma remoção feita pela voz não entra nessa conta; só a do painel.
