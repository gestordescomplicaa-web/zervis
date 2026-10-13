# 0028 — Manutenção, um estado do Zé: o centro do próprio código

- Data: 13/10/2026
- Status: **Aceito** (pedido do usuário: o modo manutenção como estado do Zé, em laranja, e o
  ambiente pronto para quem instala pedir ao Zé que se adapte; aplicar não pode derrubar as
  sessões de outros projetos)

## Contexto
O modo manutenção nasceu levando a voz a uma sessão externa; hoje usa a sessão própria do Zé, na
cópia isolada (ADR 0026). Mas ele era um detalhe da voz: o painel não mostrava, e Diagnosticar e
Aplicar funcionavam fora dele. Aplicar reinicia o serviço e, com isso, interrompia sessões de
outros projetos no meio do trabalho (visto no registro de 13/10/2026).

## Decisão
1. **Manutenção é um estado do Zé**, como ouvir ou falar: ligado por voz ("Zé, entra no modo
   manutenção") ou no painel (Autodesenvolvimento, "Entrar em manutenção"), e mantido entre
   reinícios. Mudar o estado pelo painel vale só no próprio PC.
2. **Laranja em todo lugar**: o anel e o holograma (já âmbar), o acento do painel e a marca
   "Zérvis · Manutenção".
3. **O que só vale nele**: Diagnosticar e Aplicar. Fora do estado, a página mostra o que há e
   oferece entrar.
4. **Aplicar não interrompe ninguém**: com sessões de outros projetos trabalhando, o Zé espera
   ("Aplico quando terminarem") e aplica sozinho quando ficarem livres; enquanto espera, não
   aceita trabalho novo nelas. Sair da manutenção cancela a espera.
5. **Aplicar e reiniciar, só do próprio PC.** Pela voz, só o microfone do PC aplica, e nunca a
   zona protegida: "eu revisei" falado não vale como revisão. Voz do celular ou texto digitado
   recebem "Aplique no computador." A zona protegida só entra pelo painel, no PC, com a revisão
   marcada (essência, item 7).
6. As travas do ADR 0026 continuam: cópia isolada, `make check`, zona protegida com revisão,
   volta automática.

## Consequências
- O diferencial do Zé fica visível: quem instala já tem o ambiente para pedir que ele se adapte,
  com regras para não quebrar o próprio sistema.
- O painel está no limite do orçamento de abertura (130 KB); a próxima função global precisa
  liberar espaço (mover páginas raras para `web/paginas/`).
