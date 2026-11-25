# 0132 — A identidade do painel: casca nova, voz no topo, menu por áreas

- Data: 25/11/2026
- Status: **Aceito** (protótipo aprovado por quem usa; `docs/plano-design.md`).
- Ajusta o ADR 0128 (o mapa das páginas segue igual; só a ordem e as áreas do menu mudam).

## Contexto

A nota do front era ≈ 6,3 contra Hermes, OpenBot e Grok Bot: cara de painel de administração, menu
longo, ajustes misturados ao trabalho em cada página e a voz escondida no rodapé do menu. As
direções visuais sorteadas pela skill de design foram recusadas: o problema era organização, não
cor. Quem usa aprovou um protótipo simples e elegante, com o menu recolhível, os avisos na tela e a
voz no centro.

## Decisão

1. **Casca:** o menu lateral por áreas (Início, Conversa, Imersão; Trabalho, Negócio, Casa, O Zé;
   Ajustes), com ícones de traço e o botão **Recolher menu**, lembrado no navegador. A **barra do
   topo** leva o título da página, o Zé (o anel com o estado escrito e o modo de fala), Conectar voz
   e **Falar**: a voz sai do rodapé do menu e fica à vista em toda página.
2. **Visual:** escuro sólido, sem vidro nem brilho; o ciano só no principal e no que está vivo, o
   âmbar no que espera você; a fonte **Geist** servida pelo próprio painel (nada de fora); os ícones
   num único `icones/lucide.svg` gerado por `android/icones.py`. Os avisos entram pela direita,
   abaixo da barra do topo; as páginas entram com um movimento curto.
3. **Peso:** o estilo das Sessões e do Autodesenvolvimento (lista, terminal, arquivos) vai para
   `sessoes.css`, carregado com a página como o do terminal; a abertura continua abaixo dos 130 KB.
4. **Proteções:** a Imersão não muda (a casca a envolve sem tocar nas linhas dela, conferido por
   `test_imersao_protegida.py`); os botões das páginas pedem o mesmo ao Zé (`painel_contratos.json`,
   só a casca regravada).
5. **Sem interruptor de visual antigo:** dois visuais em paralelo dobrariam o código e a chance de
   erro; a volta, se preciso, é reverter o PR.

## Consequências

- Os grupos do menu deixam de abrir e fechar: com o menu recolhível, não são mais necessários.
- Próximos passos (`docs/plano-design.md`): Início com "Precisa de você" e a central de avisos no
  sino; Marketing com o trabalho separado dos ajustes; Ajustes num lugar só, com busca.
