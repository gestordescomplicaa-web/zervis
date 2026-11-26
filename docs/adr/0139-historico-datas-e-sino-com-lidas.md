# 0139 — O histórico inteiro no Início, a data no chat e o sino com lidas

- Data: 25/11/2026
- Status: **Aceito** (protótipo aprovado em imagens no mesmo dia).
- Segue os ADRs 0133 (a central de avisos) e 0136 (o Início é a conversa).

## Contexto

Quem usa perguntou se a conversa do Início era "rolagem infinita, salvando tudo". O Zé guarda
cada troca desde a primeira (`<dados>/conversas/conversas.db`), mas o chat lia só o dia de hoje,
no máximo as últimas 200 falas: à meia-noite o chat esvaziava, e num dia cheio (276 trocas num
dia de novembro) as primeiras sumiam da tela. Os dias anteriores só voltavam pela voz
(`historico_buscar`). Cada fala mostrava só a hora.

O sino contava as pendências do "Precisa de você" e o número nunca baixava: um item só saía ao
ser resolvido na página dele. Não havia "visto" nem "lido", e os avisos do Zé sumiam à meia-noite.

## Decisão

1. **O chat busca o que veio antes.** A leitura `conversa` continua sendo o dia de hoje (agora
   com `dia`, o hoje do Zé, no fuso dele); rolando para cima, o painel pede
   `conversa/anteriores` com o horário da primeira fala da tela e recebe até 80 itens anteriores,
   dia a dia, sem separar um pedido da resposta (os dois têm a mesma hora), e `mais` enquanto
   houver o que buscar. Nas boas-vindas de um dia sem conversa, rolar para cima também abre o
   dia anterior. O que sai da leitura de hoje (virou o dia, ou passou de 200) continua na tela.
2. **A data no fio.** Cada dia abre com a data ("Hoje", "Ontem", "Segunda-feira, 23 de novembro";
   de outro ano, com o ano), presa no topo enquanto o dia passa; a hora de cada fala mostra a data
   completa ao parar o mouse ("25/11/2026 às 14:32"). As funções ficam em `modulos/datas.js`,
   fora da abertura.
3. **O sino como notificação de app.** Cada item e cada aviso tem uma chave que muda quando o que
   ele diz muda (um lead que manda outra mensagem, mais uma sugestão de memória). O número conta
   só o que ainda não foi **visto**; abrir o sino marca o que aparece como visto e zera o número.
   Cada item fica com o ponto até ser clicado (**lido**); "Marcar todas como lidas" tira todos.
   O que precisa de você continua na lista até ser resolvido. Os avisos do Zé dos últimos 7 dias
   (até 60) ficam agrupados por dia, com a hora.
4. **As marcas ficam no Zé** (`zervis/avisos/lidos.py`, `<dados>/avisos-lidos.db`, SQLite), pela
   escrita `avisos/marcar`: o computador e o celular veem o mesmo. Cada marca vale 30 dias. Os
   avisos de antes da primeira leitura contam como lidos, para o sino não começar cheio.

## Consequências

- `Conversas.dias()` lê os dias distintos direto no SQLite (`Documentos.distintos`), sem carregar
  as trocas.
- A resposta do Zé a "o que precisa de mim?" não muda: ela lê a lista, não as marcas.
