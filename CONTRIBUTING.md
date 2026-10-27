# Como contribuir com o Zérvis

O Zérvis é de código aberto (AGPL-3.0-or-later), e contribuições são bem-vindas: correção, teste,
documentação, ideia. Quem mantém decide o que entra; este guia diz como propor para a decisão ser
rápida.

## Antes de começar

- Leia o [README](README.md), o [roteiro](docs/roteiro.md) (para onde o projeto vai) e a
  [essência](docs/essencia.md): nenhuma mudança pode contrariá-la.
- Uma mudança grande (nova função, mudança de arquitetura) começa numa *issue*, para combinarmos o
  caminho antes de você gastar tempo. Correções pequenas podem ir direto num PR.
- Falha de segurança **não** vai numa issue pública: veja [SECURITY.md](SECURITY.md).

## Como propor

1. Faça um *fork*, crie uma branch a partir da `master` e faça a mudança.
2. Rode `make check` (formatação, lint, tipos, testes, Go): precisa passar. A CI do GitHub roda o
   mesmo a cada PR; PR com a CI vermelha não é revisado.
3. Abra o PR pelo modelo. Diga o que muda, por quê e como você provou. Mudança de comportamento
   traz teste; correção de erro traz o teste que falhava antes.
4. Quem mantém revisa. Só entra na `master` com a CI verde e a aprovação de quem mantém.

## Regras do projeto

- **Nada de uma pessoa fixa no código:** nome, fuso, caminho, serviço. O que é de quem usa vem da
  configuração; o `tests/test_usuario.py` vigia isso.
- **Dados do usuário nunca no repositório:** ficam nas pastas XDG `zervis`. Chaves e senhas nunca
  entram em commit, log, teste ou exemplo.
- **Código de terceiros** entra só com a licença compatível (AGPL-3.0-or-later; ver
  [ADR 0013](docs/adr/0013-agpl-e-piper-dentro-do-ze.md)) e o aviso de autoria em [THIRD_PARTY.md](THIRD_PARTY.md).
- **Linguagem de produto na interface:** títulos pelo que a função é, estados em uma ou duas
  palavras, mensagens curtas e factuais, sem tom coloquial. Detalhe técnico vai para a
  documentação. As regras completas estão no [CLAUDE.md](CLAUDE.md).
- **Engenharia:** siga o [docs/06-qualidade.md](docs/06-qualidade.md). Decisões ficam em
  [docs/adr](docs/adr); mudou de ideia, escreva um ADR novo.

## Ambiente de desenvolvimento

```sh
uv sync && npm ci
make check
uv run python -m zervis     # o painel abre em http://127.0.0.1:8795/
```

Em um servidor, use o [guia de VPS](docs/vps.md).

## Atualizar uma instalação

`git pull` na pasta do Zé e reiniciar o serviço (`systemctl --user restart zervis`). Quem muda o
próprio Zé pelo autodesenvolvimento trabalha numa cópia isolada, em branches `ze/…`; o que está
decidido e o que falta sobre atualizar sem perder essas mudanças está no
[ADR 0036](docs/adr/0036-contribuicoes-e-atualizacoes.md).
