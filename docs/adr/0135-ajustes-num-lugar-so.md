# 0135 — Os Ajustes num lugar só, com busca

- Data: 25/11/2026
- Status: **Aceito** (protótipo aprovado; quarto passo de `docs/plano-design.md`).
- Segue os ADRs 0132 a 0134. Ajusta o ADR 0128 (o mapa ganha as páginas "de dentro").

## Contexto

Os ajustes ocupavam uma área inteira do menu (Perfil, Modelos, Voz, Atualizações) e o resto
ficava espalhado: as redes sociais, o Marketing, a Prospecção, os Conectores. Para achar "o modo
de fala" ou "a chave do Pixabay" era preciso saber em que página ele morava.

## Decisão

1. **Um item Ajustes** no rodapé do menu, sempre à vista e com o ponto de versão nova. Perfil,
   Modelos, Voz e Atualizações saem do menu e abrem a partir dele (o topo mostra "Ajustes ›
   Voz"; o item Ajustes fica aceso).
2. **A página Ajustes** (`paginas/ajustes.js`): os assuntos em cartões (Voz, Modelos, Perfil,
   Conectores, Redes sociais, Marketing, Prospecção, Atualizações), cada um com os seus ajustes.
   A busca filtra por assunto e por ajuste, sem acento. Um ajuste abre a página dele já no
   cartão certo, com um destaque breve; os do Marketing abrem na aba Ajustes.
3. **As páginas não mudam:** cada uma continua com as mesmas chamadas e o mesmo endereço
   (`#voz`, `#modelos`…); o atalho do Zé e os links entre páginas seguem valendo.
4. **O mapa (ADR 0128):** `Pagina.dentro` diz de onde se abre a página que não está no menu. O
   teste confere que o menu é igual às páginas sem `dentro`, que toda página de dentro abre de uma
   do menu e existe; o Zé lê "Voz (em Ajustes)".

## Consequências

- Página nova de ajustes entra na lista `ASSUNTOS` de `paginas/ajustes.js` (e no mapa, com
  `dentro="ajustes"`, se sair do menu).

## Ajuste de 25/11/2026: os cartões

Os ajustes eram etiquetas soltas, e as descrições repetiam a lista em três linhas. Agora cada
cartão tem o ícone, o título, uma linha de descrição (o que é) e a lista dos ajustes, em colunas
que se encaixam. Cada assunto em `ASSUNTOS` leva também as palavras da busca (o que não cabe na
descrição: "n8n", "Deepgram", "assinatura"). Na busca, um nome de ajuste mostra só os ajustes que
batem; sem nenhum, o assunto inteiro.
