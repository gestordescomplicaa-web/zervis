# 0122 — Os avisos do Instagram na hora

- Data: 23/11/2026
- Status: **Aceito** (pedido de quem usa, 23/11/2026).
- Muda o item 1 do [ADR 0118](0118-comentarios-viram-conversa.md) (a conferência a cada dois
  minutos) e vale também para a conversa no direct ([ADR 0119](0119-conversa-no-direct.md)).

## Contexto

O Zé conferia os comentários e o direct a cada dois minutos. Quem usa quer a resposta no momento
do comentário, não uma ronda periódica. A Meta avisa na hora por webhook, e o Zé já tem um
endereço fixo na internet (o túnel, usado para a Meta buscar as imagens e os vídeos).

## Decisão

1. **Rota pública** `/instagram/webhook` no painel, sem entrar: o `GET` devolve o desafio só a
   quem tem o token de verificação que o Zé gera; o `POST` só vale assinado com a chave secreta
   do app (`X-Hub-Signature-256`, HMAC-SHA256 do corpo). Sem a chave, nada é aceito.
2. **O aviso só acorda os ciclos que já existem** (comentários e direct), que leem tudo pela API
   com as mesmas travas. O conteúdo do aviso não é usado como dado: um aviso forjado com a
   assinatura certa só adiantaria uma conferência. Avisos que chegam durante uma volta viram uma
   volta a mais. Os da própria conta (a resposta pública do Zé, o eco da mensagem dele) não
   acordam ninguém.
3. **A conferência periódica vira rede de segurança:** depois do primeiro aviso assinado, passa a
   cada 30 minutos (um aviso perdido não fica sem resposta). Sem os avisos configurados, continua
   a cada dois minutos: o Zé funciona para quem não fizer a configuração na Meta.
4. **No painel** (Marketing, cartão Comentários do Instagram, "Resposta na hora"): a URL de retorno
   e o token de verificação para colar no painel de apps da Meta, e o campo da chave secreta do
   app. Salvar a chave assina a conta nos avisos de `comments` e `messages`
   (`POST me/subscribed_apps`). O estado: "Não configurado", "Aguardando o primeiro aviso",
   "Recebendo".
5. Estado em `<config>/instagram-webhook.json` (0600); a chave nunca volta para a tela.

## Como configurar (painel de apps da Meta)

1. No app, Instagram → Configuração da API com login do Instagram → Configurar webhooks: cole a
   URL de retorno e o token de verificação mostrados no Zé e clique em Verificar e salvar.
2. Assine os campos `comments` e `messages`.
3. Copie a chave secreta do app do Instagram (na mesma página) e salve no Zé.
4. O app precisa estar no modo Ativo (Live) para a Meta mandar avisos de contas sem papel no app.

## Consequências

- Precisa do endereço fixo (o túnel com domínio próprio, ou a VPS). Sem ele, o cartão pede para
  ativar o acesso de qualquer lugar.
- Se a chave estiver errada, os avisos são recusados e o painel mostra quantos; a conferência
  periódica de dois minutos continua até o primeiro aviso assinado.
