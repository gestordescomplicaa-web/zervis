# 0029 — Central de avisos: como o Zé narra várias sessões pela voz

- Data: 13/10/2026
- Status: **Aceito**, implementado em 13/10/2026 (auditoria de voz, passo 3: com a sessão respondendo, o Zé disse "A sessão
  Universo - Teste terminou. Oi, Kiko! Como você está?". Quem ouve não sabe quem está falando,
  e com três sessões ao mesmo tempo os avisos se acumulam sem ordem)

## Contexto
Hoje cada evento vira um aviso solto, falado na ordem em que chega. O fim de uma sessão em Mãos
livres lê o começo da resposta dela **na voz do Zé**, como se fosse ele falando. Não há
prioridade (um pedido de aprovação espera atrás de um "terminou"), nem agrupamento (três sessões
que terminam juntas viram três falas seguidas), nem um jeito de pedir "o próximo" ou "o que ela
disse".

O Zé é para ser um orquestrador por voz: quem usa precisa entender, só de ouvido, **quem**
precisa de **quê**, e decidir o que fazer, uma coisa por vez.

## Proposta

1. **O Zé narra; nunca imita.** Toda fala sobre uma sessão começa pelo nome dela e é em terceira
   pessoa, feita para ouvir: "A Universo respondeu um cumprimento." ou "A Loja terminou:
   corrigiu o login e os testes passaram." A resposta da sessão não é lida como está: vira um
   resumo de uma frase (pelo modelo da voz rápida, barato; sem ele, a primeira frase limpa).
2. **Uma fila só, por prioridade.**
   - **Urgente:** aprovação pedida, falha, créditos esgotados. Sai primeiro, assim que o Zé
     termina a frase em curso.
   - **Lembrete:** tem hora marcada; sai em seguida.
   - **Fim de tarefa:** espera a vez.
3. **Revisão de 15/10/2026, pedida pelo usuário:** avisos de sessões saem individualmente,
   automaticamente, por prioridade e ordem de chegada. Três sessões concluídas geram três
   resultados, sem exigir "começa" ou "próximo". Outros avisos acumulados ainda podem formar
   uma oferta. A escrita da fila é serializada, inclusive entre instâncias do mesmo arquivo.
4. **Quem usa conduz, por voz:** "sim" ou "começa" (o primeiro), "próximo", "o que a Loja
   disse?" (o resumo maior), "depois" (guarda para mais tarde), "responde que sim" ou "manda
   continuar" (vai para a sessão do aviso, que fica em foco).
5. **Um som curto antes de cada aviso de sessão**, diferente do bip de ouvir: dá para saber,
   sem prestar atenção nas palavras, que é uma novidade e não uma resposta.
6. **Por modo de fala** (ADR 0018, revisto em 15/10/2026): Normal e Mãos livres anunciam o nome
   e um resumo do resultado, mesmo com a sessão aberta. A narração considera o pedido original
   e a resposta e preserva impedimentos, trabalho parcial e verificações pendentes. Sem o
   modelo, cita uma frase da resposta com preferência por ressalvas; não trata o fim do turno
   como prova de que o pedido foi cumprido. Silencioso continua só na tela.
7. **Na tela**, cada aviso aparece na Conversa com o nome da sessão, e o que ainda espera fica
   marcado até ser ouvido ou dispensado.

## Exemplo com três sessões

> *(toque)* Zé: "A Site pede aprovação para rodar a migração do banco."
> Você: "O que exatamente?"
> Zé: "Ela quer executar o comando de migração na base de testes."
> Você: "Pode."
> *(a Loja e o Blog terminam enquanto isso)*
> *(toque)* Zé: "Resultado da sessão Loja. Ela corrigiu o login e os testes passaram."
> *(toque, depois da primeira fala)* Zé: "Resultado da sessão Blog. Ela preparou o rascunho;
> a publicação ficou pendente."

## Como foi feito
- Sem serviço externo: a fila é a de sempre (`jarvis/avisos/fila.py`, um JSON em disco), agora
  com prioridade, manchete, sessão e detalhe; o resumo de uma frase sai do mesmo modelo pequeno da
  revisão (`jarvis/avisos/central.py`); sem ele, a citação marcada ("Ela informou:").
- "sim", "começa", "próximo" e "depois" só valem por 45 s depois de uma oferta; "próximo aviso",
  "quais são os avisos" e "o que ela disse?" valem sempre.

## Consequências
- Cada aviso de fim de tarefa custa uma chamada curta ao modelo da voz rápida (o resumo).
- As regras de fala do ADR 0027 (manchete, uma repetição, sem duplicados) continuam valendo
  dentro da fila.
