# 0038 — Integrações como código: o Zé escreve, um executor sem modelo roda

- Data: 19/10/2026
- Status: **Proposta** (pedido da pessoa em 19/10/2026: "não depender totalmente do n8n"; o Zé
  olha a documentação e cria, sem integrações nativas, e economiza tokens). O webhook (decisão 6)
  toca a zona protegida (essência, item 5) e só entra com a pessoa revisando.
- Complementa o [ADR 0037](0037-integracao-com-sistemas.md): ali, o caminho MCP; aqui, o caminho
  "API direta".

## Contexto

O ADR 0037 resolveu o uso de sistemas pelo MCP: o cérebro e as sessões chamam as ferramentas do
fornecedor. Falta o trabalho repetido, como "chegou um lead no formulário, cria no CRM e avisa no
WhatsApp" ou "todo dia às 7h, puxa os pedidos do ERP e atualiza a planilha". Hoje esse trabalho só
roda passando pelo modelo:

- As automações têm dois tipos (`jarvis/automacoes/jobs.py`): `lembrete` (sem modelo) e
  `pergunta` (o cérebro responde, só com ferramentas de leitura). Não há um tipo que chame uma API
  sem modelo.
- Cada execução pelo modelo custa tokens, demora segundos e pode sair diferente da anterior. O
  Hermes mostra o teto disso: cerca de 73% de cada chamada é custo fixo (ferramentas e prompt), e
  cada tarefa do cron sobe um agente novo.

O que foi pesquisado em 19/10/2026:

| Opção | Por que não é a base do Zé |
|---|---|
| **n8n** | Licença fair-code (Sustainable Use License), não é open source. Permite montar fluxos na instância do cliente, mas não hospedar os fluxos e as credenciais de vários clientes na sua instância e cobrar pelo serviço, nem embutir o n8n num produto. Fica como destino quando o cliente já usa: desde a 2.13 ele tem servidor MCP para criar fluxos. |
| **Motor próprio com nós visuais** (HTTP, IF, Switch, editor) | O caro não são os nós, é o que fica embaixo deles: fila durável, novas tentativas, efeito único, webhooks seguros, credenciais por cliente, histórico, isolamento e editor. Seria um segundo produto. E o editor visual é para humanos; quem escreve aqui é o Zé, e a língua dele é código. |
| **Windmill** (AGPLv3) | O mais próximo do que queremos: primeiro código (Python e TS), webhook por script, fluxos com novas tentativas, MCP. Exige Postgres e um serviço a mais, demais para quem instala sozinho no PC (ADR 0032: sem banco com servidor). Fica como destino para quando o volume pedir. |
| **Activepieces** (MIT), **Kestra** (Apache 2.0) | Visual (Activepieces) ou YAML e Java (Kestra): mais peso, menos aderência a código escrito pelo modelo. |

## Decisão

**O modelo decide uma vez, o código executa mil vezes.** Uma integração é um script que o Zé
escreve numa sessão de código, a partir da documentação da API, testa e publica. Um executor
dentro do Zé o roda por horário, webhook ou pedido, sem modelo. O Zé fica com o que já faz bem:
entender, escrever, avisar.

1. **Novo tipo de automação: `integracao`.** Ela mora no projeto do cliente, sob
   `<projeto>/integracoes/<nome>/`, versionada no Git do projeto:
   - `main.py`: uma função `main(...)` cujos argumentos são a entrada e o retorno (JSON) é a
     saída. É o mesmo contrato do Windmill, o que deixa o script portátil (decisão 10).
   - Dependências declaradas no próprio arquivo (bloco `# /// script` da PEP 723), instaladas pelo
     `uv` num ambiente só daquela integração, nunca no do Zé.
   - `integracao.toml`: nome, descrição, gatilhos, nomes dos segredos, tempo limite, novas
     tentativas e concorrência.
   - `testes/`: entradas de exemplo com a saída esperada, rodadas sem rede (respostas da API
     gravadas).
2. **Quem escreve é o Zé, pelo método.** A skill `integrar-sistema` ganha o caminho "API direta →
   integração": ler a documentação, escrever `main.py` e os testes, provar com uma chamada real
   de leitura e só então propor a publicação. A conversa pode pedir ("cria uma integração que...")
   e o cérebro abre a sessão daquele projeto.
3. **Rascunho e versão publicada**, como no agente de atendimento (ADR 0031, item 8). O que roda
   é sempre a versão publicada, fixada pelo commit. **Publicar** exige os testes passando e a
   aprovação da pessoa: na tela, ou falada com o nome da integração e o que ela escreve (por
   exemplo, "cria contatos no CRM"). Integração que só lê pode ser publicada pelo Zé depois dos
   testes, e a publicação fica registrada.
4. **Execução isolada do Zé:**
   - Cada execução roda em processo próprio, com tempo limite (padrão 60 s, máximo 15 min) e
     limites de tamanho de entrada e saída.
   - O ambiente começa vazio: só recebe os segredos declarados no `integracao.toml`, resolvidos
     dos arquivos 0600 (como os conectores, ADR 0037). Nunca herda o ambiente do Zé, que tem o
     token do Claude, as chaves e o token da Central.
   - Um segredo só vale para os projetos a que pertence (o mesmo `projetos` dos conectores).
5. **Fila e histórico em SQLite**, sem Redis e sem Postgres (ADR 0032):
   - Uma tabela de execuções em `<dados>/automacoes/`, com integração, versão, gatilho, estado
     (`na_fila`, `rodando`, `ok`, `erro`, `cancelada`), tentativa, duração, saída resumida e erro.
     A entrada é guardada com limite, e os valores de segredo nunca.
   - Nova tentativa com espera crescente só para falha transitória (rede, 429, 5xx, tempo
     esgotado). Um erro do próprio script não é repetido.
   - Cada execução recebe um identificador estável (`ZE_EXECUCAO`), que o script usa como chave
     de efeito único nas APIs que aceitam (`Idempotency-Key`). Uma nova tentativa usa o mesmo
     identificador.
   - Concorrência: uma execução por integração de cada vez (padrão) e um teto geral pequeno.
     Execuções vencidas com o Zé parado rodam uma vez ao subir, como as automações de hoje.
6. **Webhook** (zona protegida, essência item 5):
   - A rota `/gancho/<id>` é a segunda rota do painel aberta sem cookie, depois da volta do OAuth
     (ADR 0037).
   - O `<id>` é um segredo aleatório de 32 bytes por integração, que a pessoa troca quando
     quiser. Quando o fornecedor assina o pedido (Stripe, GitHub, Meta), a assinatura também é
     conferida (HMAC, declarado no `integracao.toml`).
   - Só aceita `POST`, com corpo limitado e limite de pedidos por minuto. Responde `202` logo
     depois de pôr na fila, sem esperar a execução.
   - Um gancho desconhecido ou uma assinatura errada recebem a mesma resposta (`404`), e a
     tentativa fica registrada.
   - O que chega é dado, nunca ordem: o webhook não fala com o cérebro, só alimenta a fila.
   - No PC, o webhook precisa do endereço público do túnel. O fixo é o passo 5 do roteiro.
7. **O modelo só entra quando o script pede.** Para o passo que exige julgamento (classificar uma
   mensagem, extrair campos de um texto), o script chama `ze.julgar(pergunta, formato)`. A chamada
   vai a uma API local do executor, com token próprio, e é respondida pelo motor rápido do Zé
   **sem ferramentas**, com saída num formato JSON declarado. O consumo entra na conta do projeto.
   Assim, o custo em tokens fica proporcional ao julgamento, não à integração inteira.
8. **Registro e avisos** (essência, item 6):
   - Cada execução gera uma linha na Atividade, e o detalhe fica no histórico.
   - A primeira falha depois de um sucesso vira aviso, e falhas repetidas não repetem o aviso. Uma
     integração que falha 5 vezes seguidas é pausada, com aviso.
   - O resultado nunca é falado por padrão. Uma integração pode declarar `avisar = "sempre"`.
9. **Painel:** a página Automações mostra as integrações com estado ("Ativa", "Pausada", "Com
   erro"), últimas execuções, **Rodar agora**, **Pausar**, **Publicar** e o endereço do webhook
   (**Copiar**, **Trocar endereço**). O cérebro ganha as ferramentas `integracoes_listar` e
   `integracao_execucoes` (livres) e `integracao_rodar` (aprovação, se a integração escreve).
10. **Portátil para fora do Zé.** Como o contrato é o mesmo do Windmill (`main()`, dependências
    no arquivo), uma integração pode ser levada para um Windmill na VPS quando o volume ou o
    número de clientes pedir. Isso fica para um ADR próprio, com medição. No n8n, quando o cliente
    já usa, o Zé monta o fluxo lá pelo MCP do n8n (ADR 0037), e o script não é usado.

## O que não fazer

- Editor visual, nós no estilo do n8n ou uma linguagem de fluxo própria. Quando uma integração
  tem vários passos, eles ficam no código, em funções.
- Redis, Postgres ou um serviço de fila à parte.
- Embutir o n8n ou qualquer motor de licença incompatível.
- Rodar o script dentro do processo do Zé, ou com o ambiente dele.
- Passar pelo modelo em cada execução.

## Consequências

- O custo de uma integração em tokens fica concentrado em escrevê-la, e depois só no
  `ze.julgar`, quando usado.
- O Zé passa a ter código de cliente rodando sem ninguém olhando. Os testes, a versão fixada, a
  pausa depois de 5 falhas e o ambiente limpo são o que torna isso aceitável.
- Isolamento: com o ambiente limpo, o script não recebe segredos de outros projetos, mas ainda
  roda como o mesmo usuário e consegue ler arquivos dele, como as sessões (ADR 0037). Para
  fechar isso, a etapa E4 propõe o `bwrap` (bubblewrap), presente no Omarchy e no Ubuntu.
- Alto volume (milhares de execuções por hora) não é o alvo desta versão. O sinal para levar ao
  Windmill é a fila acumulando ou o tempo de espera passando de um minuto.

## Plano

Uma etapa por vez, cada uma com `make check` passando e prova real (ADR 0032).

| Etapa | Escopo | Pronto quando |
|---|---|---|
| E1 | Executor: tipo `integracao`, `integracao.toml`, `uv` com PEP 723, ambiente limpo com os segredos declarados, tempo limite, histórico e fila em SQLite, novas tentativas, `ZE_EXECUCAO`. Gatilhos por horário e **Rodar agora**. | Uma integração de exemplo (ler uma API pública e gravar um arquivo) roda por horário; um teste prova que o script não vê variáveis do Zé; uma falha de rede é repetida e um erro do script não é; um reinício do Zé no meio da fila não perde execução. |
| E2 | Método e publicação: caminho "API direta" na skill `integrar-sistema`, rascunho e versão publicada, testes obrigatórios, página Automações e ferramentas do cérebro. | Pela conversa, o Zé cria numa sessão uma integração com uma API real de leitura, os testes passam, ela é publicada e roda; a página mostra as execuções. |
| E3 | Webhook (com a pessoa revisando) e `ze.julgar`. | Um `POST` com assinatura certa entra na fila e responde `202`; um com assinatura errada recebe `404` e fica registrado; `ze.julgar` devolve JSON no formato pedido e o consumo aparece no projeto. |
| E4 | Isolamento com `bwrap`: só a pasta da integração e a rede; o resto do disco fica fora. | Um teste prova que o script não lê `<config>/` nem a pasta de outro projeto. |

## Em aberto (para a pessoa decidir)

- **Aprovação para publicar:** a proposta é que publicar uma integração que **escreve** sempre
  pergunte, e que a que só **lê** seja publicada pelo Zé depois dos testes. Ou toda publicação
  pergunta?
- **Isolamento:** E4 entra antes de abrir o webhook para clientes (mais seguro) ou depois (mais
  rápido)? A recomendação é antes.
