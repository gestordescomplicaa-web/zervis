# 0036 — Código aberto: como a comunidade contribui e como o Zé se atualiza

- Data: 16/10/2026
- Status: **Aceito** quanto às contribuições; **em aberto** quanto a atualizar quem personaliza o
  Zé (ponto 3). Pedido da pessoa em 16/10/2026: "colocar público no Git e começar então a
  atualizá-lo, com as travas, para que outros usuários me ajudem a melhorar o código".

## Contexto

O repositório era privado. Para a instalação de um comando (ADR 0034, etapa I3) e para a
comunidade ajudar, ele passa a ser público. Isso pede regras claras de quem muda o quê, e uma
resposta para quem usa o autodesenvolvimento (o Zé muda o próprio código numa cópia isolada).

## Decisão

1. **Toda mudança entra por pull request na `master`**, sem push direto, nem de quem mantém.
   A branch `master` fica protegida:
   - exige a CI verde (`check`: formatação, lint, tipos, testes com o painel num Chromium e Go);
   - exige a aprovação de quem é dono do código (`.github/CODEOWNERS`);
   - proíbe force-push e exclusão;
   - exige as conversas do PR resolvidas.
   Quem mantém pode passar por cima só em emergência (a proteção não vale para administradores,
   porque quem mantém é uma pessoa só; se o grupo crescer, passa a valer).
2. **Quem contribui** segue o [CONTRIBUTING.md](../../CONTRIBUTING.md): fork, `make check`, PR pelo
   modelo. Falha de segurança vai pelo relato privado ([SECURITY.md](../../SECURITY.md)).
   Mudança grande começa numa issue.
3. **Atualizar sem perder o que é seu** (em aberto). Hoje, atualizar é `git pull` e reiniciar.
   Quem personaliza pelo autodesenvolvimento trabalha em branches `ze/…` (cópia isolada), e
   aplicar traz o commit para a branch da instalação; um `git pull` com mudanças próprias pode
   conflitar. Princípios, a decidir em ADR próprio quando houver o primeiro caso real:
   - o que é de quem usa (perfil, chaves, memória, skills) está fora do repositório e nunca
     conflita;
   - mudanças próprias no código ficam em commits da instalação, e a atualização é um *merge* que
     o próprio Zé faz numa cópia isolada, roda o `make check` e só então aplica;
   - conflito que o Zé não resolve sozinho vira pergunta à pessoa, nunca perda silenciosa.
4. **Antes de abrir o repositório:** varredura de chaves, senhas, IPs e dados pessoais na árvore e
   em todo o histórico (feita em 16/10/2026: nada encontrado; só dados fictícios de teste), e a
   decisão sobre o e-mail dos autores dos commits, que fica público junto com o histórico.

## Consequências

- Quem contribui tem um caminho curto e o mesmo portão de qualidade de quem mantém.
- A `master` nunca recebe código sem teste verde e sem revisão.
- O ponto 3 fica registrado como risco conhecido: até ele ser resolvido, quem personaliza o código
  precisa resolver conflitos de atualização à mão.
