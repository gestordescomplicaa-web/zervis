# Integrar um site ao Zé

O Zé cuida do site e do blog pela aba Marketing (ADR 0091). É o site que se integra ao Zé, e não
o contrário: o Zé não sabe nada de um site em particular. Ele lê o que o site declara num arquivo
`zervis.json` na raiz do repositório, na branch base.

## O que o site precisa ter

- Um repositório git com o GitHub como `origin`, acessível pelo `gh` da máquina do Zé.
- Uma branch base que publica: o merge nela põe o site no ar (na Vercel, a branch de produção).
- Para o blog: um manual do redator e uma pasta de artigos em Markdown com cabeçalho YAML.

## O `zervis.json`

```json
{
  "zervis": 1,
  "blog": {
    "manual": "docs/blog-agente.md",
    "artigos": "content/blog",
    "modelo": "content/blog/_modelo.md",
    "validar": "npm run blog:check -- {slug}",
    "instalar": "npm ci",
    "campos": {
      "titulo": "title",
      "categoria": "category",
      "data": "publishedAt",
      "rascunho": "draft"
    },
    "marcador": "[[AUTOR:"
  }
}
```

| Campo | Obrigatório | O que é |
|---|---|---|
| `zervis` | sim | A versão do contrato. Hoje, `1`. |
| `blog` | não | Sem ele, a aba só aceita "Mudar o site". |
| `blog.manual` | sim | O manual que a sessão segue à risca: foco editorial, regras de escrita, categorias, cabeçalho, corpo do PR. |
| `blog.artigos` | sim | A pasta dos artigos. Arquivos que começam com `_` não são artigos. |
| `blog.modelo` | não | O artigo-modelo que a sessão copia. |
| `blog.validar` | não | O comando que valida um artigo; `{slug}` vira o nome do arquivo sem `.md`. A sessão o roda sem pedir. |
| `blog.instalar` | não | O comando que instala as dependências (`npm ci`). A sessão o roda sem pedir. Os comandos não podem ter caractere de shell (`;`, `&&`, `|`). |
| `blog.campos` | não | Os nomes, no cabeçalho, do título, da categoria, da data e do rascunho. Padrão: `title`, `category`, `date`, `draft`. |
| `blog.marcador` | não | O começo do trecho de experiência real. A pessoa responde antes de aprovar, ou o trecho sai na publicação. |

Os caminhos são relativos à raiz do repositório e não podem sair dela.

## O que o Zé faz e o que fica com a pessoa

1. Cada pedido vira uma sessão de código numa cópia isolada e protegida, a partir da branch base.
2. A sessão escreve, valida e faz o commit. Ela não envia a branch: grava o corpo do PR em
   `.ze-pr.md` na raiz da cópia (convém pôr no `.gitignore` do site).
3. Quando a sessão termina, o Zé envia a branch (`blog/<slug>` ou `site/<pedido>-<id>`) e abre o
   PR. O artigo só sai com o rascunho ligado.
4. A pessoa revisa no preview e aprova ("aprovado" pela voz, ou "Publicar" na aba Marketing).
   - No artigo, a sessão tira o rascunho e encaixa as respostas às perguntas de experiência, se
     vierem.
   - O Zé envia direto à branch base, sem commit de merge: o autor é o dos commits, o que evita o
     bloqueio de autor da Vercel no plano Hobby.
   - Depois confere o deploy de produção pelo GitHub e avisa.
5. Se a base exigir PR (proteção de branch), o envio direto é recusado: publique pelo GitHub com
   "Rebase and merge", que também preserva o autor.
