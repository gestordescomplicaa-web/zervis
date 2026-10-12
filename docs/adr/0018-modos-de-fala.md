# 0018 — Modos de fala: quando o Zé fala sem ser chamado

- Data: 12/10/2026
- Status: **Aceito** (pedido do usuário: separar notificação, resposta de sessão e mãos livres; quem
  desenvolve digitando, por voz ou misturando os dois escolhe)

## Contexto
O Zé falava toda vez que uma sessão de código terminava, com o resumo da resposta junto, mesmo com a
pessoa olhando a sessão na tela. Para quem digita, incomoda; para quem quer tocar projetos por voz,
é pouco (não há como responder à sessão sem as mãos).

## Decisão
1. **Três tipos de fala espontânea:** notificação (algo aconteceu, uma frase), urgente (alguém
   espera a pessoa: aprovação, créditos esgotados, erro) e resposta (o que o agente respondeu,
   resumido para ouvir: sem código, links nem caminhos completos).
2. **Três modos**, guardados em `<config>/fala.json` e trocados pelo painel (menu lateral e página
   Voz), por Alt+M no painel ou por voz ("modo silencioso", "modo avisos", "modo mãos livres"):
   | Modo | Notificação | Urgente | Resposta | Chamado "Ei Zé" |
   |---|---|---|---|---|
   | Silencioso | tela | tela | tela | desligado |
   | Avisos (padrão) | fala | fala | se pedir | ligado |
   | Mãos livres | fala | fala | fala | ligado |
3. **O que está na tela não é falado:** o painel avisa, a cada batida, qual sessão está aberta e à
   vista; o fim, a aprovação e os créditos dela ficam só na tela.
4. Aviso que chega no meio de uma conversa espera ela terminar (a fila durável de sempre). No
   Silencioso, o aviso fica só na linha do tempo e no painel, e a voz fica muda também para as
   respostas a pedidos escritos.
5. O agente esperando aprovação passa a avisar (hook `Notification` do Claude).

## Próximos passos (mãos livres de verdade)
- O Zé saber de qual sessão a pessoa fala (a do último aviso ou pelo nome) e repassar pedidos por
  voz; resumo para ouvir pensado pelo modelo, não só limpo.
- Aprovações por voz, sempre com confirmação.
