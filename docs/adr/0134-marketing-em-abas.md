# 0134 — O Marketing em abas: o trabalho de cada canal e os ajustes separados

- Data: 25/11/2026
- Status: **Aceito** (protótipo aprovado; terceiro passo de `docs/plano-design.md`).
- Segue os ADRs 0132 (a casca) e 0133 (o Início).

## Contexto

A página Marketing era uma coluna de treze cartões. O de Vídeos misturava criar um vídeo (tema,
entrega, palavra) com nove ajustes que valem para todos (para quem, duração, diretor, estilo,
voz, qualidade, narração, paleta e a chave do Pixabay); os Comentários do Instagram misturavam
ligar e desligar com as contas ignoradas, o roteiro do direct e a chave da Meta. Quem usa: "se eu
clico em marketing tem diversas coisas misturadas para serem configuráveis e não fica claro o que
é o quê".

## Decisão

1. **Abas:** Visão geral (o que espera o seu sim, de todos os canais, e as métricas do site),
   Blog, Vídeos, Instagram e Ajustes. A aba escolhida é lembrada no navegador.
2. **Trabalho e ajustes separados:** cada canal guarda só o que é de cada peça (criar, a lista,
   a prévia, publicar). O que se configura uma vez vai para Ajustes, por assunto: Site e blog,
   Vídeos, Instagram, Marca e Chaves e contas, com um índice no topo.
3. **Pela voz:** os cartões de criar mostram o pedido falado equivalente, só onde o Zé tem a
   ferramenta (artigo, vídeo e post, todos com o "sim" antes).
4. **As mesmas chamadas:** os campos mudaram de lugar, não de nome; cada botão pede ao Zé o mesmo
   de antes (`painel_contratos.json`; o teste abre todas as abas para contar os botões).
5. **Peso:** a aba Ajustes fica em `paginas/marketing-ajustes.js`; nenhum arquivo de página passa
   de 20 KB.

## Consequências

- O mesmo padrão (abas e Ajustes por assunto) serve para as outras páginas com muitos ajustes
  (Prospecção, Redes sociais) e para a página Ajustes unificada.
