# 0105 — Empresas e o grupo de WhatsApp de cada uma

- Data: 18/11/2026
- Status: **Aceito** (pedido de quem usa, 18/11/2026).
- Etapa 1 do [plano das empresas](../plano-empresas.md). Segue o
  [ADR 0104](0104-aprovacao-no-painel.md) (nenhum grupo aprova nada) e mantém o
  [ADR 0056](0056-arquivo-do-whatsapp.md) (os grupos só são lidos para o arquivo).

## Contexto

Quem usa o Zé faz a gestão de automação e IA de várias empresas e quer um grupo de WhatsApp por
empresa, onde o Zé entrega relatórios e, depois, tira dúvidas, sem nunca executar pedido de quem
está no grupo. Antes de qualquer mensagem, o Zé precisa saber quais são as empresas, qual grupo é
de qual, e onde fica o que pode ser mostrado a cada uma.

## Decisão

1. **Empresa** é um cadastro com o nome, o grupo ligado, a pasta do projeto nesta máquina
   (opcional) e o estado (**Ligada** ou **Desligada**). Fica em `<config>/empresas.json` (só quem
   usa lê). Ligar exige um grupo; um grupo nunca fica em duas empresas.
2. **Vitrine** é a pasta `<dados>/empresas/<id>/vitrine/`, criada com a empresa: é o único lugar
   que o grupo vai alcançar (relatórios, métricas, perguntas frequentes). Fica nos dados do Zé, e
   não dentro do projeto, como o plano previa: o projeto pode ir para um repositório, e dado de
   cliente não vai. Remover a empresa tira o cadastro e mantém a vitrine.
3. **Os grupos vêm do número conectado.** O WaCalls ganhou `GET /api/sessions/{sid}/groups`: só
   a lista dos grupos em que o número está (o nome e quantas pessoas), sem as comunidades, que
   não recebem mensagens. Nada é lido nem enviado.
4. **Página Empresas** no painel, em Trabalho: a lista, o grupo e o estado de cada uma, quantos
   arquivos a vitrine tem; adicionar, editar e remover.

## Consequências

- Nenhuma mensagem sai para um grupo nesta etapa: o envio continua recusado pelo WaCalls (só
  conversa privada). A etapa 2 abre o envio apenas para os grupos de empresas ligadas.
- O número do Zé é o que entra nos grupos. Manter o seu número pessoal conectado ao mesmo tempo
  (duas sessões do WaCalls) continua pendente; não é preciso para os grupos.
