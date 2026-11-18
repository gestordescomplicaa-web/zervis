# Plano — o Zé nos grupos das empresas que você gere (18/11/2026)

**Estado:** etapas 1 e 3 feitas em 18/11/2026 ([ADR 0105](adr/0105-empresas-e-grupos.md) e
[ADR 0108](adr/0108-ze-nos-grupos.md)); as etapas 2 e 4, propostas. Parte da conversa com o Zé pelo WhatsApp ([ADR 0102](adr/0102-conversa-pelo-whatsapp.md))
e da aprovação só no painel ([ADR 0104](adr/0104-aprovacao-no-painel.md)), e muda a regra do
[ADR 0056](adr/0056-arquivo-do-whatsapp.md) (hoje o Zé lê os grupos e nunca responde neles). Cada etapa entra com o seu ADR e os testes na porta de
qualidade.

## O pedido

Quem usa o Zé faz a gestão de automação e IA de várias empresas. Cada empresa já tem um projeto
no Zé, com a sessão, os conectores (MCP), os fluxos do n8n e o acompanhamento. A ideia é ter um
grupo de WhatsApp por empresa, com o dono e a equipe, onde o Zé:

- **entrega relatórios e métricas** daquela empresa, no horário combinado;
- **tira dúvidas e responde leituras** sobre o que já foi publicado para ela;
- **nunca executa pedidos** de quem está no grupo. Pedidos com efeito continuam só com você,
  pela voz, pelo painel ou pela sua conversa com o Zé no WhatsApp.

## O que já existe e o que falta

| Peça | Hoje | Falta |
|---|---|---|
| Uma sessão por empresa | Sessões isoladas por projeto, protegidas por padrão (ADR 0074) | Ligar o projeto a uma empresa e a um grupo |
| Conectores por empresa | Só os marcados para o projeto, pela ponte, com a chave da sessão (ADR 0076) | Nada: o grupo **não** usa os conectores (ver a regra 2) |
| Fluxos do n8n | O Zé constrói e vigia (ADR 0038), com a fila durável (ADR 0069) | Um fluxo poder publicar um relatório para a empresa |
| Grupos no WhatsApp | O WaCalls captura os grupos para o arquivo do Zé (ADR 0056) | Responder num grupo ligado; enviar para um grupo |
| Persona por agente | O agente de atendimento tem persona, conhecimento, testes e Publicar | O mesmo modelo para o agente de cada empresa |
| Fila de mensagens | Fila em memória (1.024) e outbox no SQLite com reentrega, sem duplicar | Uma vez por grupo (hoje o agente responde uma conversa por vez) e ritmo de envio |
| Vários números | O WaCalls aceita várias sessões | O Zé usa só a primeira |

## As regras (não mudam em nenhuma etapa)

1. **Quem está no grupo não dá ordens.** O texto do grupo é entrada de fora (ADR 0073): o agente
   lê e responde, sem ferramenta que mude qualquer coisa. Pedido de ação vira um aviso para você,
   como o "passou para você" do atendimento.
2. **O grupo vê só o que foi publicado para aquela empresa.** O agente do grupo não alcança a
   sessão, os conectores nem a memória do Zé. Ele lê a **vitrine** da empresa: uma pasta só com o
   que você (ou um fluxo que você aprovou) publicou (relatórios, métricas, perguntas frequentes).
   Uma empresa nunca vê a vitrine de outra: as pastas são separadas, e cada grupo responde num
   processo próprio, sem acesso às outras.
3. **Só nos grupos que você ligar**, um grupo por empresa, ligado pelo painel. Grupo novo fica de
   fora até alguém decidir, como hoje.
4. **Responde só quando chamado** ("@Zé", "Zé," ou uma resposta a uma mensagem dele), com limite
   de mensagens por hora por grupo.
5. **Tudo fica registrado** na Atividade, por empresa: o que foi perguntado, o que foi respondido
   e o que foi recusado.
6. **Número do Zé, não o seu.** O whatsmeow não é a API oficial; responder muito em grupos
   aumenta o risco de bloqueio. Os grupos usam um número só do Zé, e o seu número fica a salvo.

## Etapas

### Etapa 1 — Empresas no Zé (feita em 18/11/2026)

- **Empresa** é um cadastro com: o nome, o grupo de WhatsApp ligado, a pasta do projeto e a
  vitrine (`<dados>/empresas/<id>/vitrine/`, fora do projeto: dado de cliente não vai para
  repositório). A persona do agente da empresa entra na etapa 3.
- Página **Empresas** no painel: a lista, o grupo ligado, o estado ("Ligado", "Desligado") e o
  último relatório enviado.
- **Número do Zé:** já é o conectado (ADR 0102), e os grupos são os dele. Ter o seu número
  pessoal conectado junto (duas sessões) fica para depois.
- Aceite: cinco empresas cadastradas, cada uma com o seu grupo, sem nenhuma mensagem enviada.

### Etapa 2 — Relatórios no grupo (só de ida)

É a que dá mais valor com menos risco: nada que alguém escreve no grupo é lido ainda.

- Um relatório é um **modelo** aprovado por você uma vez (o texto, as métricas, o horário) e
  gerado na vitrine por um fluxo do n8n, por uma automação do Zé ou pela sessão da empresa.
- O Zé envia ao grupo no horário, com a mesma fila durável das automações (ADR 0069).
  Relatório novo ou modelo alterado espera a sua aprovação antes do primeiro envio.
- Alerta de métrica fora do normal (um fluxo parado, uma queda de vendas) vai primeiro para
  você; ao grupo, só se você marcar o alerta como da empresa.
- Aceite: um relatório diário em cada um dos cinco grupos durante uma semana, sem envio em
  dobro nem relatório de uma empresa no grupo de outra.

### Etapa 3 — Dúvidas no grupo (leitura) (feita em 18/11/2026, ADR 0108)

- O agente da empresa responde quando chamado, com o modelo sem ferramentas, a persona dela e a
  vitrine como contexto. O que não está na vitrine ele não sabe, e diz isso.
- Pedido de ação ("Zé, pausa a campanha") recebe "Encaminhei para o gestor." e vira um aviso
  para você, com a empresa e quem pediu.
- **Fila por grupo:** cada grupo responde na sua vez, sem esperar os outros (hoje o agente de
  atendimento responde uma conversa por vez, para todos os contatos).
- **Ritmo de envio:** no máximo uma resposta a cada poucos segundos por grupo e um teto por
  hora, para o número do Zé não parecer robô em massa.
- Publicar o agente da empresa exige os testes de conversa passando, incluindo os de recusa:
  pedido de ação, pergunta sobre outra empresa e tentativa de mudar as instruções.
- Aceite: uma semana em uso, sem nenhuma ação executada por mensagem do grupo e sem nenhuma
  resposta com dado de outra empresa.

### Etapa 4 — Por empresa no painel

- A conversa de cada grupo, os relatórios enviados e os pedidos encaminhados.
- **Consumo por empresa:** os tokens gastos com cada uma (útil para cobrar o cliente).
- Exportar o histórico de uma empresa e apagar tudo dela quando o contrato acabar.

### Depois, se fizer falta

- Áudio no grupo (depende do áudio na conversa com o Zé).
- Um gestor da empresa, com o número autorizado por você, aprovar um pedido específico (por
  exemplo, reenviar um relatório). Só com ADR próprio.

## Riscos

- **Bloqueio do número:** o maior risco. Daí o número do Zé, o ritmo de envio e o limite por hora.
- **Dado de uma empresa no grupo de outra:** daí a vitrine por pasta, um processo por grupo e os
  testes de conversa com a pergunta cruzada.
- **Instrução escondida numa mensagem do grupo:** o agente não tem ferramentas; o pior caso é uma
  resposta errada, nunca uma ação.
- **LGPD:** as mensagens dos funcionários ficam guardadas. O agente se apresenta no grupo na
  primeira mensagem, e a retenção é configurável por empresa.

## O que muda na nota

No placar do plano de maturidade, o critério **Alcance** mede quem consegue instalar e usar o Zé
(instalação do zero, sistemas, cérebro pela API). Os grupos não mudam isso. Eles sobem:

- **Proposta e diferencial:** o Zé passa a ser a central de um gestor com vários clientes,
  coisa que nenhum dos comparados faz pronto; estimativa de 8,2 para 8,8.
- **Canais e alcance** (na comparação com os concorrentes): o Zé chega a quem não instala nada,
  o dono e a equipe da empresa; estimativa de 6,8 para 7,5.

Nota geral estimada: de 8,1 para 8,3 com as etapas 1 a 3.
