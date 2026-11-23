# 0113 — Formato, gancho, ritmo e voz dos vídeos

- Data: 18/11/2026
- Status: **Aceito** (pedido de quem usa, 18/11/2026).
- Segue a edição ([ADR 0110](0110-edicao-dos-videos.md)), a memória
  ([ADR 0111](0111-videos-na-semana.md)) e as fotos ([ADR 0112](0112-fotos-nos-videos.md)).

## Contexto

Quem usa achou os vídeos repetitivos, "vídeos prontos": o mesmo roteiro, ganchos fracos, edição
sem ritmo e a voz estranha. As causas estavam no pedido ao diretor e no motor: um esqueleto fixo
(gancho de texto, cenas, frase, o mesmo fecho), de 4 a 7 cenas em 30 s (uns 5 s cada), uma
animação por tipo, a mesma música em todo vídeo e a voz do Zé (um personagem de anime) em tudo.

## Decisão

1. **Formatos editoriais** (`zervis/video/formatos.py`): erro, lista, POV, mito, um dia, com e
   sem, pergunta e segredo, cada um com o seu esqueleto. O diretor escolhe um ("formato" no plano);
   a memória leva o formato dos últimos vídeos, e o mesmo formato do último volta uma vez.
2. **Gancho:** seis técnicas de abertura; a primeira frase com até 8 palavras; nunca saudação, nome
   da marca ou "você sabia". O vídeo pode abrir com gancho, foto, ícone, número ou frase.
3. **Ritmo:** um corte a cada 2 a 4 s; de 6 a 10 cenas em 30 s; uma frase curta por cena (até 16
   palavras).
4. **Animações novas** (`web/ritmo.js`): "cortes" (cada palavra sozinha na tela inteira, num corte
   seco a cada palavra), "carimbo" (o destaque bate na tela, com tremor e clarão) e o fecho
   "chamada" (o convite enorme na cor da marca e a seta para o link).
5. **Som:** a trilha varia por vídeo (progressão, tom e andamento pela semente) e cada ação tem o
   seu som: o corte seco e o carimbo batem, a carta estala, as outras transições passam com o
   whoosh, as palavras em cortes estalam.
6. **Voz do vídeo:** um seletor no cartão Vídeos com a voz do Zé, o Cadu (local) e as suas vozes
   do Fish Audio; a última escolhida vale para os vídeos agendados. Só as suas: a biblioteca
   popular do Fish tem vozes que imitam pessoas reais, e um vídeo de marca não fala com a voz de
   ninguém.

## Consequências

- Dois vídeos do mesmo tema saem com formato, gancho, ritmo, música e fecho diferentes.
- O custo por vídeo é o mesmo (um plano do Opus, um pouco mais longo).
- Uma voz do Fish nova para os vídeos entra salvando a voz na conta do Fish.
