# 0124 — As fotos do Pixabay nos vídeos

- Data: 23/11/2026
- Status: **Aceito** (pedido de quem usa, 23/11/2026).
- Soma uma fonte ao [ADR 0112](0112-fotos-nos-videos.md); mantém o [ADR 0121](0121-fotos-livres-sem-credito.md).

## Contexto

Só com fotos de domínio público do Commons (ADR 0121), o acervo é pobre para um vídeo de negócio:
muitas buscas não acham nada que sirva (o gancho fica só com texto), e o que vem é foto de arquivo
ou de governo. O Pexels pausou as chaves novas; o Openverse devolveu buscas vazias.

## Decisão

1. **O Pixabay é a primeira fonte da busca livre**, com a chave de quem usa
   (`<config>/pixabay.key`, 0600), posta no cartão Vídeos ("Fotos do Pixabay": a chave é
   conferida numa busca antes de guardar). A licença dispensa o crédito, como o ADR 0121 pede.
2. **As mesmas regras da escolha:** as palavras do pedido nas etiquetas, nada de gente, busca
   segura, só fotos; a foto é baixada para a pasta do vídeo (o Pixabay não deixa usar o endereço
   dele direto).
3. **Nunca depende dele:** sem a chave, com a chave recusada ou sem resultado que sirva, a busca
   segue no Commons e, sem nada, a cena vira ícone, como antes.

## Consequências

- Duas ou três buscas por vídeo, bem dentro do limite do Pixabay (100 por minuto).
