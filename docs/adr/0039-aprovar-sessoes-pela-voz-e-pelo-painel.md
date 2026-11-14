# 0039 — Aprovar os pedidos das sessões pela voz e pelo painel

- Data: 27/10/2026
- Status: **Aceito como direção** (pedido da pessoa em 27/10/2026: "a ideia é que eu possa
  trabalhar tanto do PC quanto por voz pelo celular"). Plano E1 a E3; a E0 (prova) está feita.
- Complementa o [ADR 0037](0037-integracao-com-sistemas.md) (política por ferramenta nos
  conectores) e o [ADR 0029](0029-central-de-avisos.md) (quando o Zé fala).

## Contexto

Uma sessão do Claude Code pede permissão no terminal para o que não está liberado. Hoje o Zé só
avisa "a sessão X está esperando sua aprovação", e quem aprova é a pessoa, no terminal. Longe
do PC, a sessão trava: na sessão `meu-n8n`, em 27/10/2026, uma consulta de leitura ficou quase
5 minutos parada esperando o "sim".

A política do conector (ADR 0037) tira a maior parte das perguntas: no `n8n-teste`, 31
ferramentas livres, 12 em aprovação (publicar, rodar de verdade, arquivar, mexer em dados) e 15
bloqueadas. O que sobra são justamente as que a pessoa quer decidir, de onde estiver.

## Prova (E0, 27/10/2026, Claude Code 2.1.291)

Numa pasta de teste, com o Claude Code de verdade num terminal (como as sessões do Zé), um MCP
de mentira e o gancho `PermissionRequest`:

| Teste | Resultado |
|---|---|
| 1. O gancho responde "permitir" | A ferramenta MCP roda sem janela ("Allowed by PermissionRequest hook"). |
| 2. O gancho responde "negar" com mensagem | Não roda; a sessão recebe a mensagem e para. |
| 3. O gancho espera 20 s e não decide | **A janela do terminal aparece já, enquanto o gancho espera**; sem decisão, continua lá. |
| 4. O gancho decide "permitir" depois que a janela apareceu | A janela some e a ferramenta roda. |
| 5. A pessoa responde no terminal antes do gancho | A ferramenta roda; **o gancho não é avisado** e segue até o próprio prazo. |
| 6. Gancho do tipo `http` para `127.0.0.1`, chave numa variável de ambiente | Funciona; a chave chega no cabeçalho (`${VAR}` com `allowedEnvVars`) e não aparece na linha de comando. |
| 7. Comando de terminal que pede permissão (`curl`) | Passa pelo mesmo gancho (`tool_name: Bash`). |
| 8. Os campos do pedido | Traz `prompt_id`, `tool_name`, `tool_input`; **não traz `tool_use_id`** (o exemplo da documentação traz). |
| 9. O `timeout` do gancho `http` | Em **segundos**: com 15, uma resposta aos 10 s valeu; com 5, não. |

No Codex 0.159 (mesma data): o `PermissionRequest` dispara para ferramentas MCP em `prompt` e
para comandos fora da caixa de segurança (`tool_name: Bash`), com `turn_id` e sem
`tool_use_id`; permitir e negar funcionam; a pergunta dele só aparece **depois** que o gancho
volta sem decisão; no Esc, o gancho não é encerrado, mas o `Interrupt` dispara com o mesmo
`turn_id`; `approve` libera uma ferramenta (e `auto` não); só há gancho de comando.

Conclusões: o terminal e o Zé valem ao mesmo tempo, e o primeiro que responde decide; nada
trava se o Zé não responder. O Zé precisa descobrir sozinho que a pessoa já respondeu no
terminal (teste 5).

## Decisão

1. **A ponte.** Cada sessão do Claude ganha um gancho `PermissionRequest` do tipo `http` para
   uma rota local do Zé, com uma chave própria da sessão numa variável de ambiente do terminal.
   A rota só aceita `127.0.0.1` e a chave daquela sessão. O pedido entra numa fila e o gancho
   espera a decisão até um prazo (5 minutos); sem decisão, responde vazio e a janela do terminal
   segue.
2. **O primeiro que responde decide.** Terminal, painel ou voz. O Zé retira a pergunta quando a
   ferramenta roda (o `PostToolUse` com a mesma assinatura: o nome e o resumo dos argumentos,
   já que o pedido não traz o `tool_use_id`; para as ferramentas do MCP, um gancho enxuto que
   não leva a resposta), quando o turno dela para (`Stop` com o mesmo `prompt_id`), quando
   começa outro turno (`UserPromptSubmit`) ou no fim do prazo. O `prompt_id` impede que um
   evento lido com atraso leve o pedido de um turno novo. Uma decisão atrasada não vale.
3. **A frase é do Zé, não do modelo.** Montada da ferramenta e dos argumentos de verdade, nunca
   da `description` que o modelo escreve. Diz o que acontece se aprovar: "publicar: o fluxo
   passa a rodar com clientes reais"; "rodar de verdade: envia, cria, cobra"; um comando, o
   comando inteiro. O que não cabe numa frase curta (um comando longo, uma edição grande) não é
   aprovado pela voz: "está na tela".
   **Revisto em 13/11/2026.** Na prática, quase todo comando real tem um `/`, um `;` ou um `|`,
   e a sessão por voz parava a cada passo: o "aprova tudo" pulava justamente esses pedidos.
   - O comando que não cabe numa frase é dito pelo que faz ("rodar um comando que lê arquivos
     e roda o npm", `permissoes.resumo_do_comando`) e se aprova pela voz. O comando inteiro fica
     no painel.
   - Só fica na tela o perigoso (`permissoes.PERIGOSO`): apagar em massa, `sudo`, rodar o que vem
     da internet, `push --force`, `reset --hard`, escrever em pastas do sistema.
   - As edições do Codex ("mudar 2 arquivos do projeto") vão pela voz.
   - Numa sessão protegida (ADR 0074), mudar um arquivo também vai pela voz, e ler (`cat`, `ls`,
     `grep`, `sed -n`...) roda sem pergunta, porque o agente só enxerga a cópia do projeto.
   **Aprovar sozinho (13/11/2026, a pedido).** Mesmo pela voz, o Zé lia cada pedido em voz alta.
   Numa sessão protegida, ele passa a aprovar sem perguntar os comandos, as edições e as páginas
   lidas que não são perigosos (`Permissoes.automatico`, ajuste `oficina.aprovar_sozinho`,
   ligado por padrão). Cada um vai para a Atividade como "aprovado sozinho (sessão protegida)".
   Continuam com a pessoa: o perigoso, as ferramentas de conector (que agem fora: publicar um
   fluxo, cobrar um cliente), as perguntas e os planos. A essência segue: ação perigosa pede
   confirmação, e tudo fica registrado.
   **A fala é curta (13/11/2026, a pedido).** Ouvir o comando, mesmo resumido, cansava. Num
   comando, numa edição ou numa página, o Zé diz só "Tem uma aprovação do pedido X. Aprovo?", e
   no perigoso "Tem uma aprovação com risco no pedido X. Veja no painel.". O que é exatamente
   fica no painel e na Atividade. No conector, a consequência continua sendo dita ("publicar o
   fluxo X: ele passa a rodar de verdade"), porque ela é curta e decide a resposta.
4. **Onde pergunta.** No painel, no cartão da sessão: Aprovar e Negar (também pelo celular, com
   a senha e o código do autenticador). Pela voz quando o Zé pode falar (ADR 0029); no
   Silencioso, pelo app de voz; sem nenhum dos dois, só no painel e no terminal. Uma pergunta
   por vez, na ordem de chegada, com o nome da sessão.
5. **O que aprova.** Só um "sim" claro; "não" nega. Silêncio ou fim do prazo **não** negam
   aqui: a pergunta sai da voz e fica no painel e no terminal, porque a pessoa pode estar no PC.
   O Zé não ouve o próprio eco como resposta (como já faz no CONFIRMANDO). Na prática (E2):
   - o "sim" e o "não" logo depois da pergunta viram um comando local, sem o cérebro, e valem
     só para ela, por 45 s (a janela abre quando o Zé fala a pergunta);
   - a janela pega outras falas, então só uma resposta curta (até cinco palavras) e que não seja
     pergunta decide; o sim precisa vir no começo e ser claro ("vai chover amanhã?" e "faz um
     resumo" não aprovam); negação ou correção em qualquer lugar nega; "não entendi" repete;
   - "ok, pode" responde à sessão antes de virar o "ok" que encerra a conversa;
   - "Ei Zé, aprova" e "nega" valem a qualquer momento para o pedido que espera; com pedidos de
     várias sessões, o Zé pede o painel;
   - "aprova tudo" (ou "sim, aprova tudo" logo depois da pergunta) aprova todos os pedidos que
     esperam na mesma sessão e cabem numa frase; o resto fica no painel (27/10/2026). O cérebro
     não aprova nem nega: um "aprova" que chega até ele não aprova nada, e ele diz isso;
   - pela voz, nunca um ID: o nome do fluxo, se o pedido traz, ou em que n8n; um comando com
     caminho, redirecionamento ou aspas (que a fala encurtaria) só avisa.
6. **Rodar sozinho até o resultado.** Os comandos de teste e verificação do projeto passam sem
   pergunta, como regras de permissão do Claude (por exemplo `Bash(make check)`,
   `Bash(uv run pytest:*)`, `Bash(npm test:*)`), escolhidos por projeto. No n8n, testar com dados
   de exemplo (`test_workflow`) já é livre. A sessão itera sozinha e só pergunta o que mexe
   fora do rascunho.
   Pesquisar e abrir páginas (WebSearch e WebFetch) também passam sem pergunta (27/10/2026): só
   leem, e uma sessão de pesquisa pedia aprovação a cada site, nove numa só.
7. **O que não muda.** O bloqueado no conector nunca chega; os comandos proibidos do Zé
   continuam proibidos e a voz não os libera.
8. **Registro.** Cada pedido entra na Atividade: o que foi pedido, quem decidiu e por onde
   (voz, painel, terminal ou prazo).
9. **O Codex no terminal pelo mesmo caminho** (27/10/2026, Codex 0.159). Ele tem o mesmo
   gancho `PermissionRequest`, com a mesma resposta, mas só de comando: um comando fixo do Zé
   repassa o pedido à mesma rota, com a chave, o endereço, o prazo e o arquivo de eventos no
   ambiente. Fixo porque o Codex pede para confiar em cada gancho novo ("Hooks need review"):
   a pessoa confia uma vez por conta, e o Zé avisa quando essa tela aparece. As ferramentas do
   conector vão todas, por `approval_mode`: livres `approve`, o resto `prompt` (passa pelo
   gancho), bloqueadas em `disabled_tools`. Sem terminal (`codex exec`), só as livres, como
   antes.

10. **O formulário de perguntas e o plano** (12/11/2026). Visto em 09 e 10/11/2026: o Claude Code
    mandava o formulário de perguntas (`AskUserQuestion`) ao gancho, o Zé dizia "usar a ferramenta
    AskUserQuestion" e aprovava com um "sim" sozinho, e o Claude Code descartava a aprovação: o
    formulário ficava no terminal. Essas duas ferramentas só seguem com os argumentos de volta
    (`updatedInput`): o formulário com as respostas (`answers`, pela pergunta, com o rótulo da
    opção; várias opções separadas por vírgula), e o plano (`ExitPlanMode`) com o próprio plano.
    - **Formulário:** o Zé lê uma pergunta por vez, com as opções, e termina em "Qual delas?". A
      fala seguinte é a escolha: o nome da opção, a posição ("a segunda"), "outra resposta: ..."
      para texto livre, ou "cancela"/"no terminal" para deixar o formulário no terminal. Uma
      fala que não bate com uma opção não responde nada: ele pergunta de novo. "Aprova" não
      responde um formulário. No painel, um botão por opção (caixas quando vale mais de uma),
      outra resposta escrita e "Responder no terminal".
    - **Plano:** "A sessão terminou o plano e quer começar. O plano está na tela. Aprovo?", e o
      "sim" de sempre.
    - Respondidos no terminal, os dois saem do painel e da voz pelo nome da ferramenta (o que
      roda já traz as respostas).

    Prova (12/11/2026, Claude Code 2.1.322, terminal real): o gancho respondeu o formulário
    ("Which color do you prefer?" → "Blue") e a sessão seguiu com a resposta; e aprovou o plano
    (`updatedInput` com `plan` e `planFilePath`), e a sessão saiu do modo plano e criou o
    arquivo. No `claude -p` o formulário não existe.

## Consequências

- A sessão não trava longe do PC, e no PC nada muda: a janela do terminal continua.
- Quem está perto do celular e diz "sim" aprova. É o mesmo risco das aprovações faladas do
  cérebro; as ações perigosas continuam no conector como aprovação ou bloqueio.
- A fila e a rota são novas superfícies; a rota só escuta em `127.0.0.1` e cada sessão tem a
  sua chave.
- Depende do gancho `PermissionRequest` do Claude Code e do Codex; uma mudança nele quebra a voz,
  mas não a sessão (a pergunta do terminal continua).
- No Codex, a pergunta dele só aparece depois que o gancho volta: enquanto o Zé espera, o
  terminal não pergunta nada. Daí o prazo menor (2 minutos) e a faixa no painel, logo acima do
  terminal da sessão, para quem está no PC.

## Plano

| Etapa | Escopo | Estado |
|---|---|---|
| E0 | Prova no Claude Code real (acima). | Feita em 27/10/2026. |
| E1 | Rota, fila e chave por sessão; o gancho nas sessões; Aprovar e Negar no painel; retirar a pergunta quando o terminal responde; Atividade; comandos de teste liberados. | PR #49. Provada com o Claude Code real: aprovado pelo painel, rodou sem tocar no terminal; aprovado no terminal, saiu do painel. |
| E2 | A pergunta falada (item 3), "sim" e "não", a fila, o Silencioso pelo app. | PR #50. Provada com o Claude Code real (só o áudio simulado): "Sim, pode." aprovou e a ferramenta rodou. |
| Codex | O mesmo no Codex do terminal (item 9). | Provada com o Codex 0.159 real em 27/10/2026: a livre rodou direto, a que pede aprovação esperou o Zé e rodou com o "sim", o Esc retirou o pedido, a bloqueada nem apareceu. |
| Formulário e plano | O item 10: as respostas pela voz e pelo painel, e o plano. | Provada com o Claude Code 2.1.322 real em 12/11/2026. |
| E3 | Extras, a pedido: "sim, sempre" (libera no conector, depois de o Zé dizer qual); Aprovar e Negar na notificação do Zé Voz. | Cada um com a sua prova. |

