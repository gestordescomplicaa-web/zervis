# 0014 — O modo imersivo dentro do Zé

- Data: 09/10/2026
- Status: **Aceito** (decisão do usuário: "faz parte do sistema"; o holograma evolui a partir
  deste repositório, para todos)

## Contexto
O modo imersivo (o holograma do Zé, o Núcleo com os orbes e a tela movida pelas mãos) era o
Barehands modificado, num repositório e num serviço à parte, com a pasta de estado e o manifesto
dentro da própria pasta do código. Quem instalasse o Zé não recebia o holograma, e o Zé novo
gravava o estado numa pasta que o holograma não lia (a boca não mexia).

## Decisão
1. **O imersivo é código do Zé**, em `jarvis/imersivo/`: o servidor (`servidor.py`), a calibração
   das mãos e a luz da câmera (`maos.py`), a página, o avatar e a mídia de exemplo (`web/`), as
   ferramentas de linha de comando (`bin/`) e os testes da página no Chromium (`tests/imersivo/`,
   `make check-imersivo`). AGPL-3.0 como o Zé (ADR 0013), com os avisos de autoria do original
   (Jared Rhodenizer) e das modificações (gdautomacao.ia) em cada arquivo e em `THIRD_PARTY.md`.
2. **O Zé sobe o servidor como processo filho** (`jarvis.imersivo.Imersivo`) e o reinicia se ele
   cair. Se a porta 8794 já estiver ocupada, o Zé não sobe o seu e avisa no log.
3. **Dados de quem usa, fora do código:** estado em `<dados>/imersivo/state` (a mesma pasta em que o
   Zé grava falando, ouvindo, expressão e a onda da voz) e o manifesto dos orbes em
   `<dados>/imersivo/barehands.json`. Sem manifesto, vale `jarvis/imersivo/barehands.padrao.json`,
   o mesmo que o Zé usa para os nomes falados (`jarvis/rosto/manifesto.py`).
4. **O servidor segue o padrão do projeto:** tipado (mypy strict), lint do ruff, validação de
   pedido sem `assert` (que some com `python -O`). A página segue em JavaScript sem build.

## Consequências
- Melhorar o holograma é mexer em `jarvis/imersivo/web/` e rodar `make check-imersivo`.
- O repositório `~/Work/barehands` deixa de ser a fonte; o serviço `barehands` à parte sai.
- Ficaram de fora: modelos 3D pessoais do Acervo, as variações do chimpanzé ainda em teste e o
  `.blend` de origem do avatar (entram quando o autor decidir publicá-los).
