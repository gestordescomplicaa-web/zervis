# 0091 — Marketing: o site e o blog de quem usa, sempre por Pull Request

- Data: 13/11/2026
- Status: **Em validação**: testado com um repositório e um `gh` de mentira e, só leitura, com o
  repositório real de um site; falta o primeiro artigo de verdade.

## Contexto

Quem usa quer que o Zé cuide do site da empresa, comece pelo blog e depois crie e publique as
postagens. O site dele já traz o manual do agente redator (`docs/blog-agente.md`, o contrato do
blog) e o modelo de artigo (`content/blog/_modelo.md`): cada artigo é um Markdown, a aprovação é
o merge de um PR, o preview da Vercel mostra o rascunho e o build recusa artigo malformado ou com
marcador de experiência real por preencher.

## Decisão

1. **Aba Marketing** no painel (em Trabalho): o site (a pasta do repositório e a branch base),
   o novo pedido, os pedidos em andamento, os PRs abertos e os artigos da base, com o estado
   (publicado, agendado, rascunho) e a contagem por categoria. Pela voz: `marketing_situacao`
   (livre, só lê), `marketing_pedir` e `marketing_abrir_pr` (pedem o sim).
2. **Cada pedido é uma sessão de código** numa cópia isolada (e protegida, ADR 0074), a partir
   da base do GitHub, não da pasta como ela está. O artigo segue o manual do próprio site; a
   mudança no site segue as instruções do projeto. A sessão valida, faz o commit e escreve o
   corpo do PR em `.ze-pr.md`, sem publicar.
3. **O Zé abre o PR**, com o `gh` desta máquina (o repositório pode ser privado): a branch vai
   como `blog/<slug>` ou `site/<pedido>-<id>`, e o artigo só sai com `draft: true`. Publicar é o
   merge, feito por quem usa.
4. **Nada do site no código:** a pasta, a base, as categorias e as regras de escrita vêm da
   configuração (`<config>/marketing.json`) e do manual do próprio site.

## Consequências

- Enquanto a base não tiver o manual do blog, a aba mostra "Sem o manual do blog" e só aceita
  mudanças no site.
- O link do preview fica no PR, pela Vercel; o Zé ainda não o lê nem avisa quando aparece.
- Entrou durante o fecho da Fase B (o plano congela funções novas até lá), a pedido de quem usa,
  com os testes na porta de qualidade.
- Próximos passos: as publicações das redes a partir dos artigos e, depois, postar sozinho.
