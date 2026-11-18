# Vídeos do Zé

Desde 18/11/2026 o Zé cria vídeos sozinho, em **Marketing → Vídeos** ([ADR 0106](../adr/0106-videos-de-marketing.md)):
o modelo escreve o roteiro e o motor de `zervis/video/` desenha, narra e monta. Abaixo, como criar
**o seu estilo** e, depois, como os vídeos de apresentação do próprio Zé foram feitos à mão, com as
mesmas peças.

## Criar o seu estilo

Um estilo é uma pasta. Copie o de exemplo e mude:

```bash
mkdir -p ~/.config/zervis/video/estilos
cp -r zervis/video/estilos/zervis ~/.config/zervis/video/estilos/meu-estilo
```

| Arquivo | O que muda |
|---|---|
| `estilo.json` | `nome` e `descricao` (como aparece em Marketing), `fontes` (do Google Fonts; as da marca do site valem antes), `onda` (a onda da voz), `trilha` (`bpm` de 70 a 160 e `energia`: `calma`, `media` ou `alta`), `tom` (como o roteiro é escrito) e `cenas` (tipos novos de cena, com o formato que o modelo deve seguir) |
| `estilo.css` | O visual, por cima da estrutura (`zervis/video/web/base.css`). As cores da marca chegam como `--fundo`, `--superficie`, `--texto`, `--suave`, `--destaque` e `--destaque2` |
| `cenas.js` | Opcional: cenas novas ou trocadas, com `Ze.cena("tipo", {montar(cena, el, ctx), render(t, d, estado, ctx)})`. `render` desenha o instante `t` (segundos desde o começo da cena) e só pode depender dele. `montar` devolve `foco` (o elemento de onde a íris abre e para onde o zoom atravessa). Para animar: `Ze.revela(el, t, quando, tipo)` com `desfoque`, `tinta`, `queda`, `lado`, `mascara` ou `giro`; `Ze.sai`, `Ze.mola`, `Ze.letras` e `Ze.animarFala` (ADR 0110) |

Uma pasta com o mesmo nome de um estilo embutido vale no lugar dele; apagar a pasta volta ao
padrão. Para ver um estilo enquanto edita, abra `zervis/video/web/pagina.html?dados=<dados.js>` no
Chromium (o `dados.js` de um vídeo fica em `<dados>/marketing/videos/<id>/`) e chame
`window.render(3.2)` no console.

Regras que valem para qualquer estilo: o texto do roteiro entra sempre como texto (nunca HTML), o
que se lê fica entre 13% e 80% da altura e fora dos 140 px da direita na metade de baixo (os botões
do Instagram), e nada de `backdrop-filter` (no Chromium sem GPU, ele custa 2 s por quadro).

## Os vídeos de apresentação do Zé

Feitos à mão, com as mesmas peças, para repetir sem redescobrir. O processo segue a
skill [`brag-slim`](https://github.com/latent-spaces/brag) (MIT): ler o projeto, escrever o
roteiro, montar com as ferramentas que já estão na máquina, conferir quadros parados e entregar o
vídeo, a capa e o texto para postar. Tudo roda local; só a narração usa a nuvem (a voz do Zé).

| Vídeo | Formato | Narração | Página | Roteiro |
|---|---|---|---|---|
| Apresentação (18/11/2026) | 1920×1080, 21 s | Não | `zervis-horizontal.html` | `roteiros/zervis-horizontal.md` |
| Reels (18/11/2026) | 1080×1920, 23 s | O Zé, pela voz escolhida no painel | `zervis-vertical.html` | `roteiros/zervis-vertical.json` |

## O que precisa

Chromium, FFmpeg e o ambiente do Zé. Os scripts daqui são linhas de comando finas sobre
`zervis.video` (`narracao`, `trilha`, `captura`): o mesmo código da função de Marketing.

## Passo a passo (o vídeo vertical)

```bash
SAIDA=brag-output-$(date +%Y-%m-%d-%H%M%S)        # fica fora do git (.git/info/exclude)
PY=.venv/bin/python

# 1. A voz: cada fala começa numa batida; saem narracao.wav e narracao.js (tempos e volume)
$PY docs/video/narrar.py docs/video/roteiros/zervis-vertical.json $SAIDA/work

# 2. Quadros de conferência: cenas assentadas e meio das transições, antes do vídeo inteiro
$PY docs/video/capturar.py docs/video/zervis-vertical.html $SAIDA/work/stills \
  --tamanho 1080x1920 --dados $SAIDA/work/narracao.js --tempos 1.5,6.8,10,11.35,14.8,22

# 3. Todos os quadros, com vários Chromiums em paralelo (a duração vem do passo 1)
$PY docs/video/capturar.py docs/video/zervis-vertical.html $SAIDA/work/quadros \
  --tamanho 1080x1920 --dados $SAIDA/work/narracao.js --duracao 23 --trabalhadores 6

# 4. A trilha: música e efeitos nos cortes (os inícios das falas 2 a 5), a voz por cima
$PY docs/video/trilha.py $SAIDA/work 23 2.5,8,13,16.5 --voz narracao.wav

# 5. O MP4 e a capa (o quadro de 22 s vira também o quadro 0)
docs/video/montar.sh $SAIDA 22
```

O horizontal é igual, sem os passos 1 e `--dados`: `--tamanho 1920x1080 --duracao 21`,
`trilha.py $SAIDA/work 21 3,6.5,10.5,14.5,17.5` e a capa em 5,5 s.

## Como as peças se encaixam

- **A página é o vídeo.** `window.render(t)` desenha o instante `t` e só depende dele; as cenas
  usam o `painel.css` de verdade (cores, cartões, etiquetas, botões), com dados fictícios.
- **A voz manda no tempo.** `narrar.py` sintetiza cada fala com a voz do painel (hoje a Fish Audio,
  com `latency: normal`, melhor para gravação), corta o silêncio das pontas e põe cada fala numa
  batida de 120 BPM. A página abre cada cena quando a fala dela começa, acende a legenda palavra
  por palavra e mexe a onda com o volume real da voz.
- **A música é composta em código** (`trilha.py`): Lá menor, Am–F–C–G, bumbo, chimbal, baixo,
  acordes, arpejo e um "whoosh" antes de cada corte, todos na mesma grade. Sob a voz, a música
  abaixa cerca de 10 dB.
- **Reels:** o que é para ler fica entre 13% e 80% da altura e fora dos 140 px da direita na
  metade de baixo, onde o Instagram desenha os botões.

## Tempo e custo (no PC de quem usa: Ryzen com Radeon integrada, Chromium sem GPU)

| Etapa | Vídeo 1 (horizontal) | Vídeo 2 (vertical) |
|---|---|---|
| Narração (Fish Audio) | — | 7 s, ~330 caracteres |
| Quadros | ~25 min (um Chromium, com desfoque) | 4 min 26 s (690 quadros, 6 Chromiums, 0,39 s cada) |
| Trilha | 3 s | 2 s |
| MP4 | 30 s | 12 s |
| **Total** | **~30 min** | **~5 min** |

O que pesava era o `backdrop-filter` dos cartões no Chromium sem GPU (2 s por quadro): as páginas
de vídeo o desligam, e a captura usa vários Chromiums ao mesmo tempo.

## Conferir antes de postar

- Os quadros de conferência: nada cortado, sobreposto ou com pouco contraste.
- O arquivo: `ffprobe` mostra os quadros esperados (duração × 30) e o tamanho certo.
- A fala: transcrever `narracao.wav` com o Deepgram e comparar com o roteiro (pega pronúncia
  errada sem precisar ouvir).
- Nenhum dado real: nomes, números e mensagens são inventados.
