# 0031 — Atendimento: o Zé atende clientes no WhatsApp e no telefone

- Data: 14/10/2026
- Status: **Aceito**. Etapa 1 implementada em 14/10/2026: o WhatsApp pareado pelo QR na página
  Atendimento e as mensagens recebidas alimentando os avisos de lead quente. No mesmo dia, o
  agente com persona própria respondendo no WhatsApp em modo teste (item 7). As etapas seguintes
  estão no [plano do atendente](../plano-atendente.md).
- Substitui a fonte do [ADR 0030](0030-assistente-de-mensagens-whatsapp.md): o WaCalls, no
  lugar do WuzAPI.

## Contexto
O pedido da pessoa é ter um agente que atende clientes: responde no WhatsApp, atende ligações como
recepcionista e passa a conversa para ela quando precisa de uma pessoa, com o aviso dentro do
próprio Zé. Não é falar com o Zé por ligação: isso o painel já faz (ADR 0024).

Tudo isso já funciona no Ligatia, o sistema de atendimento por voz da mesma pessoa: o WaCalls
(chamadas e mensagens do WhatsApp em Go puro, pareado por QR), a ponte para o LiveKit e o agente
de voz (Deepgram, modelo, voz própria), com handoff. A pessoa autorizou trazer o código do Ligatia
para o Zé.

O ADR 0030 propunha o WuzAPI só para mensagens. O WaCalls faz as duas coisas, ligações e
mensagens, com um único pareamento.

## Decisão
1. **O WaCalls vem dentro do Zé** (`jarvis/atendimento/wacalls/`), com o código do Ligatia: o
   WaCalls original (MIT) mais a captura passiva de mensagens, o envio transacional e o PCM por
   WebSocket para a ponte do agente. No Zé:
   - o aparelho aparece como "Zérvis" no celular;
   - o QR sai na lista de sessões, que o Zé consulta, e não é impresso no registro;
   - ficam de fora o cliente React (o painel do Zé faz a tela) e os vetores de referência do
     codec, que pesam 6,7 MB (os testes do codec que dependem deles também ficam de fora).
2. **Compilado na máquina.** O Zé compila o WaCalls com o Go na primeira vez que a pessoa conecta,
   e de novo quando o código-fonte muda (o binário leva no nome a impressão digital do código).
   Sem Go, a página mostra "Indisponível". Um binário publicado com o Zé fica para a instalação de
   um comando.
3. **Só no próprio computador, com token.** O WaCalls não tem login próprio. O Zé o sobe no
   endereço local com um token novo a cada subida, e as mensagens chegam a um receptor local com
   outro token. Os segredos do WhatsApp ficam em `<dados>/whatsapp/wacalls.db` (0600).
4. **O atendente é separado do Zé principal.** O que chega de um cliente é dado, nunca ordem
   (essência, item 5). Nesta etapa, as mensagens só são julgadas pelo modelo sem ferramentas dos
   avisos de lead quente. O atendente das próximas etapas roda em processo próprio, com ações de
   um catálogo fechado, e fala com o Zé só por eventos (handoff, lead, resumo).
5. **Nada guardado sem motivo.** O WaCalls pergunta ao Zé se pode guardar cada mensagem. A
   resposta é sim só com os avisos de lead quente ou o agente ligados; fora disso, nada fica.
6. **Página Atendimento** (grupo Trabalho), com o estado do WhatsApp, o QR, Conectar e
   Desconectar (com confirmação), e os avisos de lead quente. Com o WhatsApp conectado, as
   notificações do sistema deixam de ser fonte dos avisos, para o mesmo contato não ser avisado
   duas vezes.
7. **O agente de atendimento** (`jarvis/atendimento/agente.py`) responde com a persona que quem
   usa define na página (ou pede ao Zé, pela ferramenta `atendente_definir`, que não liga o agente
   nem muda para quem ele responde). Roda num laço próprio, com um modelo sem ferramentas e uma
   resposta por vez; mensagens seguidas do mesmo contato viram uma resposta só. Modo **Teste**
   (padrão: só os números de teste) ou **Todos** (com confirmação). Passar para você: o modelo
   marca `[[PASSAR: motivo]]`, o agente para naquele contato, e o Zé fala só "<nome>, no
   WhatsApp, precisa de você." (o motivo fica na tela). Se você responde pelo celular, o agente
   também sai da conversa. O WaCalls ganhou o tipo de envio `atendimento_reply`. **Só conversa
   privada** (pedido de 14/10/2026): grupo, status e canal nunca chegam ao agente, com três travas
   (filtro do WaCalls por lista do que é permitido, conferência no Zé ao receber e no agente, e
   envio só para um número).
8. **O agente é um projeto** (`<raiz_projetos>/agente-de-atendimento`, Git; contrato em
   `jarvis/atendimento/modelo/AGENTS.md`). O formulário, o Zé e uma sessão de código ("Abrir
   sessão") escrevem no rascunho; os clientes só veem a versão publicada, que **Publicar** copia
   para `<dados>/atendente/publicado/` depois de todos os testes de conversa (`testes/*.toml`)
   passarem com o modelo. Ligar exige uma versão publicada. O perfil da primeira versão vira o
   projeto e a versão publicada na primeira subida.
9. **A Central de Atendimento é um serviço próprio** (`python -m jarvis.atendimento`, unidade
   `zervis-atendimento` pelo `systemd-run`; processo filho onde não há systemd). Ela mantém o
   WhatsApp e o agente; reiniciar o Zé não derruba o atendimento. API só no endereço local, com o
   token de `<config>/atendimento.token` (0600); a porta fica em `<estado>/atendimento.json`. O
   Zé busca os eventos com espera longa ("passou" vira o aviso falado; "mensagem" alimenta os
   leads quentes) e reinicia a Central quando a versão do código dela não é a dele. Testar e
   Publicar rodam no Zé, sobre o rascunho.
10. **A recepcionista** (`jarvis/atendimento/ligacao.py`, etapa 2): com "Ligações do WhatsApp"
    ligado, a Central atende as chamadas de quem o agente atende (mesmas regras do texto: modo
    teste ou todos; nunca um contato que está com você). Sem a sala do LiveKit no meio: o PCM do
    WaCalls vai direto ao Deepgram (streaming, a ligação inteira); o turno fecha no fim da fala,
    esperando quando a frase ficou pela metade; o mesmo agente responde pelo motor rápido do Zé
    (com as regras de voz no prompt), frase a frase, na voz do Cadu, num quadro de 60 ms a cada
    60 ms; o cliente interrompe e a voz para; falas seguidas antes da resposta viram um turno.
    Passar para você encerra a ligação dizendo que alguém retorna. Até duas ligações ao mesmo
    tempo, quinze minutos no máximo. Medido em 14/10/2026: 0,5 s para fechar o turno e ~2,1 a
    2,7 s até a primeira palavra pelo modelo da assinatura; com a via rápida numa chave de API, o
    tempo do modelo cai para perto do Ligatia.
11. **Voz natural e tempo de resposta, do Ligatia** (pedido de 14/10/2026, depois da primeira
    ligação real: "respondeu como se fosse texto" e "achei lento").
    - **Prompt por canal:** a ligação troca as regras de escrita do WhatsApp pelas regras de fala
      por telefone do Ligatia (uma ou duas frases, até ~20 palavras, devolver a palavra, reação
      curta antes de pensar, nada abreviado), em vez de somar as duas.
    - **Preparo da fala** (`normalizar_voz`, do Ligatia): "8h30" vira "8 horas e 30", "R$ 1.500,00"
      vira "1500 reais", "%" vira "por cento"; frase de bastidor ("devo encerrar a chamada")
      nunca vira voz.
    - **Pré-aquecimento:** a saudação já sintetizada e um motor aquecido esperando a próxima
      ligação, aquecido com a própria saudação (o histórico fica verdadeiro). Renova ao subir,
      depois de cada ligação e quando a persona ou o cérebro mudam; nunca por tempo, porque cada
      aquecimento é uma chamada ao modelo.
    - **Geração antecipada** (o `preemptive_generation` do Ligatia): com motor sem estado (API),
      quando a transcrição para de mudar por 0,25 s a resposta começa em silêncio; se o cliente
      termina com as mesmas palavras, ela já está pronta; se continua, é descartada.
    - **Reação curta:** se o modelo não respondeu em 0,8 s, toca "Uhum.", "Certo." ou "Entendi."
      (já sintetizados), e o "Entendi!" que o modelo diria em seguida não se repete.
    - **Cérebro do agente** escolhido na página Atendimento, na mesma lista das sessões (Claude e
      Codex pela assinatura) e nas chaves de API da via rápida; vale para o texto e as ligações.
    Medido em 14/10/2026 pela assinatura (Haiku 4.5): o turno fecha em 0,4 s, a reação toca em
    ~1,2 s e a resposta varia de 1,7 a 5 s, conforme o serviço. Pela API, o caminho do Ligatia.
12. **A página Atendimento, revista** (14/10/2026): um cartão por função. WhatsApp (conexão);
    Atendimento (interruptores "Responder no WhatsApp" e "Atender ligações", para quem responde e
    os números de teste); Cérebro (o modelo em destaque e as chaves de API, com Salvar, Testar e
    Remover; as mesmas da via rápida; sem a chave em uso, o agente volta ao padrão); Agente (só a
    persona, Publicar, rascunho e sessão); Testar; Com você; Memória; Avisos.
    **Memória do agente:** a conversa de cada contato, a mesma no texto e nas ligações, em
    `<dados>/atendente/conversas/` (só neste computador, separada da memória do Zé); o agente usa
    as últimas 20 mensagens. A página mostra quantos contatos e mensagens e apaga tudo com
    confirmação. O que o agente sabe da empresa vem da persona e do conhecimento.

## Consequências
- Um número de WhatsApp a mais conectado ao computador, por protocolo não oficial: o número pode
  ser restringido pela Meta. A página recomenda um número dedicado ao atendimento.
- Para usar o WhatsApp, a máquina precisa do Go (por enquanto). A primeira compilação baixa os
  módulos e leva cerca de um minuto.
- O Zé só envia as respostas do agente e só atende ligações quando a pessoa liga a opção; não
  liga para ninguém (etapa 7).
