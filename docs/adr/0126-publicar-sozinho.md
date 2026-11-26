# 0126 — As automações de marketing que publicam sozinhas

- Data: 24/11/2026
- Status: **Aceito** (pedido de quem usa, 24/11/2026).
- Muda o "publicar espera a aprovação" dos ADRs [0092](0092-blog-automatico.md) (artigos),
  [0109](0109-publicar-reels.md) e [0111](0111-videos-na-semana.md) (Reels) para as automações
  em que quem usa liga "Publicar sozinho". Cria o carrossel agendado.

## Contexto

Quem usa quer três Reels por semana (segunda, quarta e sexta) criados e publicados sem precisar
aprovar cada um, e o mesmo para os artigos do blog e os carrosséis. Até aqui, toda automação
criava e parava esperando o "aprovado"; carrossel agendado não existia.

## Decisão

1. **"Publicar sozinho" é uma opção de cada automação, desligada por padrão.** Ligá-la (no
   cartão da automação, ou pela voz, com a frase de confirmação dizendo "vai ao ar sozinho,
   sem te perguntar") é a aprovação dada uma vez por quem usa (essência: ações que publicam
   pedem confirmação; aqui ela vem ao agendar). O pedido do job guarda `"publicar": true`.
2. **Reels:** o vídeo agendado é feito na própria linha da automação e, pronto, vai ao Instagram
   (a mesma publicação de sempre). **Artigo:** a sessão fica marcada; quando o PR abre, o Zé dá
   o "aprovado" (sem respostas aos marcadores de experiência: os trechos saem) e envia à base.
   **Carrossel:** novo tipo de automação (`post`), com o tema da vez (a lista, o artigo novo do
   blog ou um assunto da linha editorial) e, com a opção, publicado ao ficar pronto.
3. **Cada publicação fica registrada** na Atividade e vira aviso (na tela e na fila); a falha
   (Instagram fora, sem endereço fixo) deixa o rascunho e avisa. Pronto com erro, não publica.
4. **Os temas não se repetem:** os Reels usam a trava do ADR 0125, que agora também considera
   os vídeos feitos antes dela (pelo título).

## Consequências

- O que vai ao ar sozinho segue o mesmo roteiro e as mesmas travas do que espera aprovação.
- Sem a opção, nada muda: publicar continua com quem usa.
