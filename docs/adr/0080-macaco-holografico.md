# 0080 — O Zé como macaco holográfico

- Data: 11/11/2026
- Status: **Aceita** (aprovado no laboratório do holograma em 11/11/2026; `tests/imersivo/test_avatar.py`).

## Contexto

O chimpanzé holográfico do Zé (cabeça feita no Blender, desenhada como constelação de pontos) não
parecia um macaco de perto: sem nariz definido, boca estranha, e a nuvem de pontos tirava a forma.
Quem usa queria algo mais bonito e que fosse, de fato, um macaco.

## Decisão

1. **O modelo:** o busto "Monkey / Australopithecus stone bust", de gamnok (Sketchfab, CC BY 4.0),
   escolhido entre os modelos livres por ter rosto de primata bem esculpido. O crédito fica em
   `avatar/LICENSE-macaco.txt` e no `THIRD_PARTY.md`.
2. **Preparado no Blender, por script** (`avatar/macaco_blender.py`, do arquivo original ao
   `jarvis-macaco.glb`, sempre o mesmo resultado):
   - reduzido a 60 mil faces, sem textura;
   - os lábios separados no vinco que a escultura já tem, de canto a canto, com a abertura da
     mandíbula como forma do próprio modelo (`jawOpen`), oval como uma boca de verdade;
   - a boca por dentro, escura, e a dentição de um chimpanzé: 32 dentes (2.1.2.3), arcada em U,
     tamanhos da odontometria da espécie, caninos arredondados para não dar cara de bravo; nenhum
     dente encosta no lábio, de boca fechada ou aberta;
   - as quatro emoções do Zé como formas: alegria, tristeza, raiva e dúvida.
3. **O visual "contorno"** (o C do laboratório): o volume escuro e a silhueta de luz forte, os olhos
   como dois pontos de luz que piscam, sobre o projetor da constelação, na cor do tema do anel.
   Com a boca fechada, os dentes e o interior não são desenhados (a luz deles vazava pela emenda
   dos lábios).
4. **A mesma interface do avatar** (`avatar/jarvis-macaco.js`, como `jarvis-chimpanze.js`): a boca
   segue a onda real da voz, as emoções vêm do Zé, o giro e a tontura pela mão continuam.
5. **Sem linhas** do Zé até os painéis em nenhuma apresentação (antes, só a abertura): cruzavam os
   outros painéis.

6. **A qualidade do laboratório no anel** (11/11/2026, depois da aprovação): o anel desenhava com
   bem menos pixels, sem o brilho (bloom) e sem a conversão para sRGB do laboratório, e o macaco
   saía escuro e de contorno duro. `avatar/jarvis-brilho.js` traz o mesmo brilho e a mesma
   conversão com fundo transparente; o desenho vai a 1,5 a 2 pixels por pixel da tela e a câmera
   chega mais perto.

## Consequências

- O chimpanzé continua no repositório (`jarvis-chimpanze.*`), sem uso, até sair numa limpeza.
- O modelo novo tem 1,5 MB.
- O brilho custa um alvo de 4 amostras e doze passes pequenos por quadro (a até 30 por segundo); a
  sombra de CSS que ele substitui também pesava na placa.
