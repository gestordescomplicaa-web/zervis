# 0077 — O painel em módulos ES

- Data: 10/11/2026
- Status: **Aceita** (o `tsc` e os 34 testes do painel num Chromium de verdade passam).

## Contexto

O painel eram 28 scripts comuns (cerca de 3.500 linhas) num escopo global só: cada arquivo usava
as funções e as variáveis dos outros pelo nome, sem dizer de onde vinham, e 27 variáveis mudavam
de valor em mais de um arquivo. Uma função de página sob demanda usada cedo demais só aparecia no
navegador. É o item "painel em módulos ES" da Frente 5 do
[plano de maturidade](../plano-maturidade.md): sem variáveis globais divididas entre arquivos e
sem passo de build.

## Decisão

1. **Cada arquivo é um módulo ES**, com `import` e `export` explícitos. Sem build: o navegador
   carrega os arquivos como estão, e o `tsc` confere os tipos como antes.
2. **Uma entrada só** (`modulos/principal.js`): importa os módulos e só então começa a navegação e
   o batimento. Assim a ordem em que os módulos se avaliam não importa.
3. **O estado mexido por mais de um arquivo fica em `modulos/estado.js`** (`compartilhado`): a
   sessão aberta, o terminal, o número da navegação, as telas de modelos e contas. Quem lê ou
   muda escreve `compartilhado.sessaoAberta`, e é fácil achar todos os lugares.
4. **As páginas continuam sob demanda** (`import()` na hora de abrir), e com elas os módulos que só
   elas usam. O que o núcleo chama de uma página ou de um desses módulos (abrir a sessão, escrever
   no terminal, desenhar os modelos) entra no registro `carregadas` quando ele carrega. A
   biblioteca do terminal (xterm) segue como script comum.
5. **Os testes do navegador** alcançam o que precisam pelos mesmos módulos, com um script que o
   Chromium roda em cada página nova; o painel não ganha nenhuma global para os testes.

## Consequências

- O painel continua abrindo leve: o núcleo (a base, a voz, a imersão, as ações e a navegação) vem
  na abertura; as páginas e os módulos que só elas usam (o terminal, os arquivos, os conectores e
  as permissões das sessões, os modelos) vêm na hora, e o núcleo os chama pelo registro
  `carregadas`. `tests/test_portal.py` segue os `import` a partir da entrada e confere o peso.
- Uma página nova é um módulo: importa o que usa e se registra em `PAGINAS`.
