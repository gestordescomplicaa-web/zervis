# Zérvis (o Zé)

Antes de codar, leia `README.md` e `docs/roteiro.md` (para onde o projeto vai, em ordem).
Regras de engenharia: `docs/06-qualidade.md` (obrigatórias). Decisões: `docs/adr/`.

- O Zé é para qualquer pessoa instalar do zero: nada de nome, fuso, caminho ou serviço de
  alguém fixo no código. O que é de quem usa vem da configuração (`jarvis/lugares.py`,
  `jarvis/usuario.py`, `jarvis/fuso.py`). `tests/test_usuario.py` vigia isso.
- Dados do usuário nunca no repositório: ficam nas pastas XDG `zervis`.
- Licença AGPL-3.0-or-later (ADR 0013): código GPL-3/AGPL-3 (Piper, Barehands) pode ser
  combinado; todo código de terceiros entra com aviso de autoria em `THIRD_PARTY.md`.
- `make check` passa antes de todo commit.
- Pedidos que começam com `[JARVIS · modo manutenção · pedido <id>]` vêm do usuário por voz,
  pelo próprio Zé: respeite a zona protegida escrita no pedido e, ao terminar, grave no arquivo
  indicado um resumo falado de um parágrafo, sem símbolos, caminhos nem códigos.
