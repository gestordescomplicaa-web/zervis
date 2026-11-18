# 0108 — O Zé nos grupos das empresas: responde quando chamado, só com a vitrine

- Data: 18/11/2026
- Status: **Aceito** (pedido de quem usa, 18/11/2026).
- Etapa 3 do [plano das empresas](../plano-empresas.md). Segue o
  [ADR 0105](0105-empresas-e-grupos.md) (o cadastro e a vitrine) e o
  [ADR 0104](0104-aprovacao-no-painel.md) (nenhum grupo aprova nada); muda o
  [ADR 0056](0056-arquivo-do-whatsapp.md), que só lia os grupos.

## Contexto

Com a empresa cadastrada e o grupo ligado, quem usa chamou o Zé no grupo e ele não respondeu: a
etapa 1 só fez o cadastro. O plano previa a etapa 3: o Zé tira dúvidas no grupo, só com o que foi
publicado para aquela empresa, e nunca executa pedido de quem está no grupo.

## Decisão

1. **Só nos grupos das empresas ligadas, e só quando chamado:** a menção ao número do Zé ou uma
   resposta a uma mensagem dele (o WaCalls marca `calls_me` na captura), ou "Zé" no começo da
   mensagem ("Zé,", "@Zé", "Ei Zé", "Oi, Zérvis"). Conversa do grupo que não chama o Zé vai só ao
   histórico curto, para ele entender o contexto.
2. **Um agente sem ferramentas, na Central** (`zervis/atendimento/grupos.py`), como o de
   atendimento: o mesmo modelo escolhido na página Atendimento, a vitrine da empresa como o que ele
   sabe (`empresas.conhecimento`: o texto "O que o grupo pode saber" e os arquivos `.md`/`.txt` da
   pasta, até 16 mil caracteres) e as regras que não mudam. Ele não alcança a sessão, os
   conectores, a memória do Zé nem outra empresa.
3. **Pedido de ação vira encaminhamento:** o agente responde "Encaminhei para o gestor." e marca o
   pedido; o Zé avisa quem usa (falado, na linha do tempo e no WhatsApp do número autorizado da
   conversa com o Zé, ADR 0102). Nada é executado pelo grupo.
4. **Duas travas de envio:** o Zé só manda ao grupo de uma empresa ligada
   (`WhatsApp.enviar_ao_grupo`), e o WaCalls só aceita um grupo que esteja na lista que o Zé grava
   a cada mudança do cadastro (`<config>/whatsapp-grupos.json`, lida a cada envio). Desligar a
   empresa vale na hora. O envio comum continua sem grupo.
5. **Ritmo:** no máximo 20 respostas por hora por grupo e uma a cada 4 s; mensagens seguidas que
   chamam o Zé viram uma resposta só; cada grupo na sua vez, sem segurar os outros.
6. **Tudo fica registrado:** por empresa em `<dados>/empresas/<id>/grupo.jsonl` (a pergunta, a
   resposta e o que foi encaminhado) e na Atividade do Zé.

## Consequências

- A qualidade das respostas é a da vitrine: vazia, o Zé diz que o gestor vai responder. O cartão
  da empresa ganhou o campo "O que o grupo pode saber".
- O número do Zé é o que responde nos grupos (o risco de bloqueio do WhatsApp fica com ele, não
  com o número pessoal de quem usa).
- As mensagens dos grupos ligados ficam guardadas (o arquivo do Zé e o registro da empresa); a
  retenção por empresa e a apresentação do Zé no grupo ficam para a etapa 4.
- Relatórios no grupo (etapa 2) ficam para depois: o envio a grupos ligados já existe.
