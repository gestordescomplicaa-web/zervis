# 0129 — A mensagem da prospecção: o que faz, por que ela, o convite e o horário

- Data: 24/11/2026
- Status: **Aceito** (pedido de quem usa).
- Ajusta a mensagem do [ADR 0127](0127-prospeccao.md).

## Contexto

As primeiras mensagens abriam com uma pergunta de diagnóstico ("qual o seu maior desafio?") e não
diziam o que quem usa oferece nem o próximo passo. Uma delas citava "reclamações sobre
precificação" da empresa. Quem usa pediu que a mensagem diga o tipo de negócio e o valor, e já
leve a agenda para um diagnóstico gratuito, com urgência.

A urgência proposta foi "estamos fazendo uma pesquisa e a sua empresa foi selecionada". A parte da
pesquisa não é verdade, e "você foi selecionado" é o padrão do golpe pelo WhatsApp: quem recebe
desconfia e denuncia, e a denúncia é o que restringe o número. A parte da escolha é verdade: o Zé
analisou as empresas do ramo na cidade e escolheu aquela por um fato dela.

## Decisão

1. **A ordem da mensagem:** quem é e o que faz (do "O que você oferece"); por que esta empresa (o
   Zé analisou as empresas do ramo na cidade e ela chamou atenção por um fato real, positivo ou
   neutro); o convite, pelo que a empresa leva da conversa; a urgência, só se houver; o fecho.
2. **Na página, o cartão Mensagem:** O que você oferece, Convite ("um diagnóstico gratuito de 20
   minutos"), Vagas (opcional, "5 diagnósticos por mês"), Link de agendamento (sem ele, o do
   direct do Instagram) e "Link na primeira mensagem".
3. **Urgência só verdadeira:** o modelo só fala em limite com as palavras de "Vagas"; sem elas,
   nenhuma urgência. Proibido: pesquisa, sorteio, seleção oficial, prêmio, reclamação de cliente,
   preço ou defeito da empresa.
4. **O link** é posto pelo código, numa linha própria antes da saída, nunca escrito pelo modelo
   (os outros links continuam sendo tirados). Com ele, o fecho convida a escolher um horário; sem
   ele, termina com uma pergunta de sim ou não para marcar.
5. **Mudou a estratégia, mudam as que esperam:** salvar um campo da mensagem reescreve as que
   ainda não saíram (aguardando aprovação ou na fila), menos as que quem usa editou.

## Consequências

- Link na primeira mensagem, vindo de um número que a pessoa não conhece, aumenta o risco de
  denúncia; a página deixa a escolha com quem usa (desligado por padrão). Com o volume baixo e a
  saída em toda mensagem, o risco fica controlado.
- A conversa depois da resposta (etapa 2) continua por fazer: quem responde sem marcar fica com
  quem usa.
