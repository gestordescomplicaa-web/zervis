# 0066 — Chamar você durante a ligação e passar para o app de voz, sem derrubar

- Data: 06/11/2026
- Status: **Em validação** (testado com a ponte de verdade, por WebSocket local, e com o app e a
  ligação simulados; falta a primeira ligação real pelo celular).

## Contexto

O agente atende as ligações do WhatsApp. Pedido de 06/11/2026: quando alguém pede para falar com
quem usa o Zé, o agente põe em espera, o Zé avisa na hora ("a Ana quer falar com você sobre o
orçamento, pode atender?") e, com o "sim", a ligação passa para ele sem cair. O que importa é
atender **pelo app Zé Voz**, no celular, e não pelo computador (para isso já existe o WhatsApp
Web).

O WhatsApp conectado é o da própria pessoa: o Zé atende na conta dela, então não há para onde
"transferir" no sentido de telefonia (o celular é a mesma conta, e o WhatsApp não transfere
chamadas). No Ligatia, a transferência para o operador era por "softphone": a ligação vivia numa
sala de áudio, a IA era um participante, e o operador entrava na mesma sala pelo navegador.

## Decisão

O mesmo princípio, com o app no lugar do navegador: **o Zé vira a ponte**. A ligação continua aberta
no WhatsApp, e o áudio passa da voz do agente para o celular.

1. **O agente chama** (`ligacao.py`): se a pessoa pede para falar com o dono (o nome vem do perfil),
   o agente diz que vai ver se ele pode atender, sem prometer, e termina com
   `[[CHAMAR: assunto]]`. A ligação fica em espera: "só mais um instante" a cada 15 s, por até
   45 s; o que a pessoa diz nesse meio só é anotado.
2. **O Zé pergunta** (`_ligacao_chamando`): pelo app conectado, falando ("Fulano, a Ana está na
   linha e quer falar com você sobre o orçamento. Pode atender?", e já ouvindo a resposta) e numa
   notificação com "Atender" e "Agora não". Sem o app conectado, não há por onde atender: o agente
   diz na hora que você não pode e anota o recado.
3. **A resposta**: pela voz (`whatsapp_ligacao`: atender, recusar ou encerrar) ou pelos botões.
   "Agora não", ou nada em 45 s: o agente diz que você não pode agora, anota o recado e combina o
   retorno; o resumo chega no fim, como em toda ligação.
4. **A ponte** (`Central._na_ponte`, `transporte/ponte.py`): com o "sim", o agente diz "pronto,
   vou te passar" e sai. A Central abre um WebSocket local (`/ponte/<chamada>`, com o token da
   API); o Zé conecta e leva a voz da pessoa ao app como leva a fala dele, e o microfone do app
   vai para a pessoa, no lugar do "Ei Zé". O app já toca e grava ao mesmo tempo, no modo de ligação
   do celular, que tira o eco: o áudio não muda nada nele. Se a sua voz atrasa mais de 2 s, sai o
   pedaço mais velho, para a conversa não ficar para trás.
5. **Durante a ligação**, os avisos do Zé esperam (`Maquina.em_ligacao`): nada fala por cima. No
   fim, eles são oferecidos ("Tenho dois avisos. Se quiser ouvir, é só pedir.").
6. **O fim**: quando a pessoa desliga, quando você toca em "Encerrar" ou diz "desliga a ligação",
   ou quando o app cai. A ligação fica guardada com o desfecho "transferida" e o que a pessoa
   disse, sem aviso falado, porque você estava nela.

## Consequências

- O app ganha a notificação da ligação (`Ligacao.java`); o áudio usa o canal que já existia.
- A ponte só existe enquanto a ligação dura e só escuta no endereço local.
- O que você diz na ponte não é transcrito; o resumo tem só o lado da pessoa.
- Atender pelo computador ficou de fora de propósito; dá para somar depois pelo mesmo caminho
  (a voz pelo navegador).

## A primeira ligação real (06/11/2026)

A ponte abriu e a ligação terminou como "transferida", mas o áudio saiu travado e com a voz
alterada. Pelos registros, com o app no modo Ao vivo, o Zé respondeu ao "sim" ("pronto,
transferi…") pelo Live **com a ponte já aberta**. A fala dele foi direto ao app:

- anunciou outra taxa (a da voz do Zé), e o app passou a tocar a pessoa, que vem a 16 kHz, nela:
  a voz alterada;
- o "fim" de cada frase silencia o microfone do celular por um instante (a proteção contra o
  eco da fala do Zé): o áudio travado para quem ligou.

Além disso, o filtro de eco e ruído do Zé tratava a voz de quem usa como se fosse um pedido
para ele.

**Correção** (`transporte/ponte.py`): enquanto a ligação está no celular, só a ponte fala com o
app. A conexão do app é trocada por uma que descarta o áudio e os sinais de taxa e de fim de frase
que não vêm da ponte; as notificações passam. A voz de quem usa vai crua (o celular já tira o
eco), e os dois sentidos começam com 200 ms de silêncio, uma folga contra os soluços da rede.
No fim, a conexão volta ao normal.
