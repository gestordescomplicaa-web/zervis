# 0072 — O autodesenvolvimento só corrige as falhas do próprio Zé, e a voz nunca fica presa nele

- Data: 09/11/2026
- Status: **Aceito** (decisão do usuário em 09/11/2026: o desenvolvimento do Zé segue pelo
  Claude Code, em PRs revisados, até uma versão estável que o satisfaça; o autodesenvolvimento
  fica com um papel menor).

## Contexto

Em 09/11/2026 o usuário passou a manhã melhorando o Zé pelo autodesenvolvimento, com o modo
manutenção ligado. Três problemas apareceram:

- **A voz ficou presa na sessão de código.** Ligado, o modo mandava à sessão tudo o que não fosse
  comando local (ADR 0028): "Sim Ei Zé.", "Existe uma possibilidade." e "Acabou o limite." viraram
  pedidos de manutenção. A fala parecia lenta porque cada frase ia a um agente de código, não ao
  cérebro.
- **"Propor como PR" abriu oito PRs com os mesmos commits** (#122 a #129), um por clique,
  enquanto os testes rodavam em paralelo sem andamento na tela. A trava e a conferência de PR
  aberto entraram no #126; o resto deste ADR trata da causa, que é o fluxo.
- **Dois desenvolvedores no mesmo repositório**: o Zé, por voz, e o Claude Code, pelo plano de
  maturidade. As mudanças de um apareciam como surpresa para o outro.

As sessões comuns já fazem o trabalho de código genérico, inclusive no próprio repositório do Zé.
O que só o autodesenvolvimento tem é o acesso ao que o Zé viveu: a Atividade, o registro técnico e
os erros da hora.

## Decisão

1. **O papel do autodesenvolvimento é corrigir as falhas do próprio Zé**: um erro do registro
   técnico ou da Atividade, uma ferramenta que falhou, um pedido que ele não soube atender, uma
   queda na nota da avaliação (Frente 3). Função nova, plano de maturidade e outros projetos ficam
   fora: são das sessões comuns e do desenvolvimento revisado.
2. **A fala comum nunca vai para a sessão de autodesenvolvimento.** O modo manutenção deixa de
   capturar a voz: com ele ligado, a fala vai ao cérebro como sempre. O pedido à sessão é
   explícito ("manda para o autodesenvolvimento corrigir…"), pela ferramenta `modo_manutencao`
   com `pedir`, que passa pela aprovação falada. A resposta a uma pergunta da sessão vai pelo
   mesmo caminho.
3. **O modo manutenção continua sendo um estado** (ADR 0028): laranja, Diagnosticar e Aplicar só
   nele. Ligado, quer dizer que a sessão de autodesenvolvimento está aberta para correções, não
   que a voz é dela.
4. **Próximos passos, na ordem:**
   - Propor como PR em segundo plano, com o andamento dos testes na página (hoje a página espera
     os testes sem dizer nada).
   - Só propor: Aplicar direto na pasta em uso sai. O GitHub passa a ser a única fonte, e a
     atualização chega pelo canal de sempre.
   - Os pedidos vindos dos próprios dados: o diagnóstico junta as falhas repetidas e propõe o
     pedido; a rodada noturna da avaliação (Frente 3) entrega os cenários que caíram.

## Consequências

- A voz não depende mais do estado do modo manutenção: o mesmo caminho e a mesma latência, ligado
  ou não.
- Um pedido à sessão custa uma frase a mais ("manda para o autodesenvolvimento") e uma aprovação.
  É de propósito: cada pedido gasta o limite de um agente de código.
- Os pedidos de voz por engano que já estão no estado (`pendentes` em
  `~/.local/state/zervis/manutencao/estado.json`) continuam lá até a sessão responder ou o modo
  ser desligado; nenhum novo entra.
- O comando local `manutencao_pedido` sai. A captura que o ADR 0028 descrevia termina aqui, e o
  resto daquele ADR continua valendo.
