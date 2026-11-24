# 0127 — Prospecção: o Zé acha a empresa, o dono e escreve a ele

- Data: 24/11/2026
- Status: **Em validação** (testes com falsos; falta a primeira busca com a chave da Apify e o
  primeiro envio de verdade).
- Etapa 1 de 2. A 2, a conversa que leva a quem respondeu até a reunião, vem num ADR próprio.
- Ajustado pelos ADR [0129](0129-mensagem-da-prospeccao.md) (a mensagem) e
  [0130](0130-quem-atende-e-os-avisos.md) (quem atende o número, a resposta automática).

## Contexto

Quem usa vende automação e IA a empresários e quer que o Zé prospecte sozinho, em Caruaru (PE):
achar empresas e falar com **quem decide** (dono, sócio, gestor), não com o vendedor ou a
recepção, que é quem atende o número da empresa. O LinkedIn não serve: no interior, a maioria dos
donos não está lá.

O que foi avaliado:

- **first-customer-finder** (github.com/Kappaemme-git/codex-first-customer-finder-skill, MIT): uma
  skill do Codex para startups acharem os primeiros clientes em posts públicos em inglês. O
  público e as fontes não servem; o **método** serve: nota de 0 a 5 em dor, encaixe, momento,
  alcance e prova, com pesos (25, 25, 20, 15, 15), travas (sem contato, alcance baixo), nenhuma
  empresa duas vezes e o envio nunca disfarçado de interesse.
- **Fontes de empresa:** o Google Maps é onde a empresa pequena está, com telefone, ramo e as
  avaliações (o sinal de dor). O raspador aberto gosom/google-maps-scraper (MIT) exige navegador
  e proxy; o ator `compass/crawler-google-places` da Apify custa centavos por empresa e não pede
  nada na máquina. Escolhida a Apify, com a chave de quem usa.
- **O dono:** o quadro de sócios da Receita (dado público, que o Zé já consulta pelo CNPJ, ADR
  0059) diz quem é o sócio-administrador; o telefone do cadastro, na empresa pequena, costuma ser
  o celular do dono (ou do contador, que o e-mail denuncia).
- **O canal:** o direct do Instagram não abre conversa com quem nunca falou com a conta (regra da
  Meta). Fica o WhatsApp conectado (WaCalls, não oficial): mensagem fria em volume derruba o
  número. Por isso, pouquíssimas por dia, uma a uma, personalizadas e com a saída.

## Decisão

1. **Página Prospecção** (Trabalho, depois de Marketing): cidade, ramos (um por linha), o que
   quem usa oferece, envios por dia (padrão 2, no máximo 5), "Ligada" e "Enviar sozinho"
   (desligados por padrão); a chave da Apify (conferida na conta antes de guardar, em
   `<config>/apify.key`, 0600) e "Adicionar empresa pelo CNPJ".
2. **O ciclo** (a cada 5 minutos, numa thread do agendador, só ligada):
   - **qualifica** até 3 empresas novas: o CNPJ pela busca do Zé (o nome e a cidade; o CNPJ
     achado só vale ativo, na cidade e com uma palavra do nome em comum), o decisor (o
     sócio-administrador; sem quadro, o titular do empresário individual; vários sócios sem
     administrador, ninguém) e os telefones (o celular da Receita que não é do contador, o do Maps,
     o fixo da Receita). O Haiku dá as notas e escreve a mensagem ao dono, pelo primeiro nome, com
     um fato da empresa, uma ideia de automação e uma pergunta para 15 minutos. Sem o dono, o
     alcance vai a no máximo 2. Abaixo de 50, sem telefone ou já nas conversas de quem usa:
     descartada, com o motivo;
   - **busca mais** no Maps quando há menos de 4 empresas esperando e a última busca tem mais de
     6 horas: 10 empresas de um ramo, em rodízio;
   - **envia** uma, se for dia útil, das 9h às 17h e abaixo do limite do dia, pelo mesmo caminho do `whatsapp_enviar` (ADR 0061): Atividade e 24 horas na lista de
     prioridade. Número fora do WhatsApp: o próximo; WhatsApp desconectado: tenta no próximo
     ciclo; nenhum número no WhatsApp: descartada.
3. **Sem "Enviar sozinho"**, a mensagem espera em "Aguardando aprovação", editável, com Aprovar e
   Descartar. Ligado, vai direto para a fila de envio. A aprovação de cada envio pela voz (ADR
   0061) não vale aqui: o "Enviar sozinho" é a autorização dada na página, como as automações que
   publicam sozinhas.
4. **Nada de disparo em massa** (o número é o de quem usa):
   - no máximo 5 por dia, uma por ciclo, sem segunda mensagem nem "follow-up" automático;
   - horários sorteados: o primeiro envio do dia num minuto entre 9h e 11h, e de 2h a 3h30 entre
     um e outro (um ritmo fixo é o que denuncia robô);
   - cada mensagem diferente (escrita para a empresa, com um fato dela), sem link;
   - a empresa fica "Envio não confirmado" **antes** do envio: se o Zé cair no meio, ela não
     volta para a fila e ninguém recebe duas vezes;
   - **freio:** 2 pessoas pedindo para não receber em 7 dias desligam a prospecção, com aviso
     para revisar a mensagem e os ramos (insistir faz o WhatsApp marcar o número). Ligada de
     novo, só as recusas novas contam.
5. **Ninguém recebe duas vezes:** o lugar do Google, o CNPJ e o telefone (DDD e os 8 últimos
   dígitos, com ou sem o nono) ficam guardados para sempre, em qualquer estado.
6. **A saída:** toda mensagem termina com "Se não fizer sentido, é só me avisar que não mando mais
   nada." Quem responde que não quer vira "Sem interesse".
7. **A resposta:** a mensagem de uma empresa contatada vira "Respondeu" na página e aviso de lead
   (pela lista de prioridade nas primeiras 24 horas; depois, pelo aviso de resposta). "Reunião
   marcada" e "Sem interesse" se marcam na página.
8. **Segurança:** o que vem do Maps e da Receita vai ao modelo entre `<<<` e `>>>`, como dado; a
   mensagem sai sem link; os dados ficam em `<dados>/prospeccao.db`.

Junto, uma correção achada na conferência da fila do WhatsApp: o WaCalls aceita até 1.200
caracteres por mensagem, e o Zé cortava em 1.900 (as respostas longas pelo WhatsApp e um envio de
18/11/2026 foram recusados inteiros, com "O WhatsApp recusou o pedido"). Agora o texto maior vai
em partes de até 1.200, cada uma com a sua chave de idempotência.

## Consequências

- O número de quem usa é o mesmo das conversas dele: o limite baixo e o espaço entre envios são
  a proteção. Subir o limite aumenta o risco de bloqueio.
- A prospecção custa na Apify (por empresa achada) e no modelo (uma consulta por empresa
  qualificada); sem a chave da Apify, só entram as empresas postas pelo CNPJ.
- Dado de sócio é dado pessoal público; a base é o legítimo interesse, com a saída em toda
  mensagem e a pessoa podendo ser descartada a qualquer momento.
- Etapa 2: quando a empresa responde, o Zé conduz a conversa até o link de agendamento, como no
  direct do Instagram (ADR 0119).
