# Zérvis (o Zé)

Antes de codar, leia `README.md` e `docs/roteiro.md` (para onde o projeto vai, em ordem).
Regras de engenharia: `docs/06-qualidade.md` (obrigatórias). Decisões: `docs/adr/`.

- O Zé é para qualquer pessoa instalar do zero: nada de nome, fuso, caminho ou serviço de
  alguém fixo no código. O que é de quem usa vem da configuração (`zervis/lugares.py`,
  `zervis/usuario.py`, `zervis/fuso.py`). `tests/test_usuario.py` vigia isso.
- Dados do usuário nunca no repositório: ficam nas pastas XDG `zervis`.
- Licença AGPL-3.0-or-later (ADR 0013): código GPL-3/AGPL-3 (Piper, Barehands) pode ser
  combinado; todo código de terceiros entra com aviso de autoria em `THIRD_PARTY.md`.
- `make check` passa antes de todo commit.

## Maturidade e comunicação clara (regra do projeto)

O Zérvis é um produto, não um protótipo. Vale para a interface e para quem desenvolve:

- **Interface com linguagem de produto.** Títulos pelo que a função é ("Reconhecimento de
  fala"), não por frases. Estado em uma ou duas palavras ("Configurado", "Não configurado").
  Descrição de uma linha: o que é e para que serve. Ações com verbo claro ("Salvar",
  "Testar conexão", "Obter chave de API").
- **Sem tom coloquial ou personificado na tela** ("o Zé não ouve", "até lá"), sem custo,
  detalhe técnico ou justificativa no texto da interface; isso vai para a documentação.
- **Mensagens de resultado curtas e factuais** ("Chave válida.", "Chave inválida.",
  "Sem conexão com o Deepgram.").
- **Referência de qualidade:** os painéis de configuração de produtos maduros (Stripe, Vercel,
  Linear): consistentes, objetivos, sem enfeite.
- **Comunicação com o usuário:** direta e curta. O que foi feito, o que falta, e no máximo uma
  pergunta com a recomendação. Sem listas de opções longas nem explicações que ninguém pediu.
- Pedidos que começam com `[Zé · modo manutenção · pedido <id>]` vêm do usuário por voz,
  pelo próprio Zé: respeite a zona protegida escrita no pedido e, ao terminar, grave no arquivo
  indicado um resumo falado de um parágrafo, sem símbolos, caminhos nem códigos.
