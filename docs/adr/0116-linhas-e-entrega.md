# 0116 — Linhas editoriais e a entrega do comentário

- Data: 19/11/2026
- Status: **Aceito** (pedido de quem usa, 19/11/2026).
- Segue a copy na tela ([ADR 0115](0115-copy-manda-na-tela.md)).

## Contexto

Quem usa é gestor de automação e IA: fala com donos de empresa e também grava vídeos sobre
ferramentas, trocando um comentário por uma entrega de verdade no direct ("comenta X que eu te
mando Y"), o que vira comentário, seguidor e contato.

## Decisão

1. **Duas linhas** (`formatos.LINHAS`): "empresarios" (a dor do negócio, o custo, a solução em
   uso, sem jargão) e "ferramenta" (o logo e o site da ferramenta, de 3 a 5 usos, para quem
   serve). Quem pede escolhe no cartão Vídeos ou pela voz; sem escolha, o diretor decide pelo
   tema.
2. **A entrega:** quem pede diz o que vai mandar e a palavra, ou o diretor sugere algo real (um
   link, um checklist, um modelo, um passo a passo), sem inventar número, preço ou bônus. A
   entrega é anunciada cedo, dizendo o que é; o fecho é sempre o "comenta", com a palavra; a
   legenda do post repete o convite. O plano guarda "palavra" e "entrega", e o painel mostra o
   que foi prometido.
3. **Print de site:** `site: <endereço>` traz o print do site (só HTTPS, atrás da trava de rede
   do ADR 0058), numa janela de navegador; até 3 por vídeo.

## Consequências

- Mandar a entrega no direct ainda é com quem usa; responder sozinho a quem comenta a palavra
  é o próximo passo (depende das permissões da Meta).
