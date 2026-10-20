# Zé · gdautomacao.ia

A interface do Zé na tela, movida pelas mãos: o anel do Zé, os círculos que
nascem dele, o quadro de vidro, o cérebro navegável e os ajustes de câmera e cores.
Roda no próprio computador; a câmera nunca sai da máquina.

## Rodar

```bash
uv run python -m jarvis.imersivo.servidor
```

Abra **http://127.0.0.1:8794/stage.html** no Chromium e permita a câmera. O próprio Zérvis
sobe o servidor no uso normal; parâmetros como resolução e câmera são opcionais na URL.

## Na tela

- **O avatar robótico do Zé**, com boca articulada acompanhando a fala e o menu
  de círculos do Núcleo (Mapa, Guia, Identidade, Acervo e Orca). Em Configurações → Visual
  é possível escolher o anel. Modelo e referência em [avatar/README.md](avatar/README.md).
- **A linha CPU · RAM · GPU · VRAM.** Todo o resto fica no menu de configurações.
- **O cérebro** (Cérebro, Trabalho e Foco) abre pelo círculo Cérebro ou por voz.

## Configurações — tecla D

Calibração das mãos, brilho da câmera (desligado, suave, médio, forte), cores (original
ou roxo, para telas claras), as baterias dos cérebros e o consumo de tokens. Tudo
funciona com a pinça, com o mouse ou com o teclado:

| Tecla | Ação |
|---|---|
| D | Abre e fecha as configurações (Shift+D: leitura de depuração) |
| K / Shift+K | Calibra as mãos / volta à calibração e à câmera originais |
| B / Shift+B | Brilho da câmera: próximo nível / nível anterior |
| T | Troca as cores |
| Esc | Fecha o que estiver aberto |

Detalhes do calibrador, da luz e do tema em [MAOS.md](MAOS.md); o cérebro
em [NAVIGATION.md](NAVIGATION.md); problemas com gestos em
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Integração com o Zé

O serviço do Zé escreve arquivos pequenos em `state/` e a página os lê por `GET /jarvis/<nome>`:
decisão, eficiência, mapa do cérebro, rotina, presença e pedidos por voz (abrir o
cérebro, calibrar as mãos, brilho da câmera, cores). O anel lê `state/state`
(`idle`, `listening`, `thinking`, `speaking`). `bin/board.sh` põe cartões no quadro e
`bin/board-state.sh` lê o que está nele.

## Gestos

Pinça curta abre e fecha; pinça e arraste move; duas mãos ampliam; jogar arremessa;
palmas juntas limpam o quadro. A pinça só vale com as pontas dos dedos encostadas
depois da calibração.

## Componentes de terceiros

Rastreamento das mãos pelo [Google MediaPipe](https://developers.google.com/mediapipe)
(Apache 2.0) e 3D pelo [three.js](https://threejs.org) (MIT), carregados de CDNs públicos.

- Rosto antigo, preservado mas sem uso (`avatar/cabeca.glb`): "Infinite, 3D Head Scan" de Lee Perry-Smith,
  licença Creative Commons Atribuição 3.0 (baseado em trabalho da triplegangers.com), obtido
  dos exemplos do three.js; detalhes em `avatar/LICENSE-cabeca.txt`.

## Licença

Software livre sob a GNU Affero General Public License, versão 3 ou posterior
(AGPL-3.0-or-later). Texto completo em [LICENSE](LICENSE).

Copyright (C) 2026 gdautomacao.ia — versão modificada e especializada para o Zé,
desde 07/10/2026.
Copyright (c) 2026 Jared Rhodenizer — obra original sob a mesma licença.

## Testes

`make check` roda a qualidade do Python e os testes de servidor. `make check-imersivo` roda
os testes da interface no Chromium sem janela, com mãos e câmera simuladas.

Otimizações e medições da interface: [DESEMPENHO.md](DESEMPENHO.md).

## Autorização local

A página envia a autorização automaticamente. Clientes HTTP do imersivo precisam de
`X-Ze-Token`, além de Host local; Origin, quando presente, deve ser o próprio imersivo. O token
fica em `<estado-imersivo>/.http-token` com permissão 0600. Não o inclua em logs nem na URL.
Os comandos `bin/board.sh` e `bin/board-state.sh` leem esse arquivo. Para outra instância, use
`ZE_IMERSIVO_ESTADO` e `ZE_IMERSIVO_PORTA`. Detalhes no [ADR 0019](../adr/0019-autorizacao-http-do-imersivo.md).
