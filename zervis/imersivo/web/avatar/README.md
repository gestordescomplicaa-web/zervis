# Avatar Zé ORCA

**Visual atual: a constelação (29/10/2026).** O mesmo chimpanzé do Blender desenhado como uma
constelação de luz, aprovada no laboratório do holograma: cerca de 4 mil pontos espalhados por
igual na cabeça, ligados aos vizinhos mais próximos (cerca de 7 mil ligações), com pulsos de luz
correndo pelas ligações, um brilho na borda, a faixa de varredura, as falhas de sinal e uma
"montagem" quando ele aparece (os pontos chegam voando e formam a cabeça). Fica em
`jarvis-constelacao.js` e só desenha: a boca, o piscar, as emoções, o pulso, a tontura e o giro
continuam vindo da mesma lógica de `jarvis-chimpanze.js`, pelos mesmos uniformes, então ele se
comporta como antes. A cor segue o tema do anel (a raiva puxa para o vermelho, a tristeza para o
azul). O rig é estático, então a pose do esqueleto é calculada uma vez; as shape keys continuam
deformando na placa de vídeo. Embaixo dele, um projetor (feixe de luz, anéis na base e partículas
subindo) e anéis orbitando a cabeça (`projetor()`), parados enquanto a cabeça balança e gira. O
desenho passa da borda do cartão (1,44 vez o cartão), e o cartão que a mão pega mantém o tamanho.
O fundo escuro da Imersão fica em `../jarvis-fundo.js`. O visual de antes, descrito abaixo, continua como estilo
`"classico"` (`criarChimpanze(T, GLTFLoader, { estilo: "classico" })`) até o novo ser aprovado.

O rosto em uso é o **chimpanzé holográfico do Zé**, só a cabeça, feito no Blender por
gdautomacao.ia (08/10/2026; o `.blend` de origem ainda não está no repositório; vista de frente em `jarvis-chimpanze-referencia.png`). `jarvis-chimpanze.glb` sai
dele por `expressoes_blender.py`, que também cria as expressões novas como variações, sem
tocar na forma da cabeça:

    blender -b <cabeca>.blend -P avatar/expressoes_blender.py -- <pasta>

e grava ao lado uma cópia do `.blend` com as chaves novas. `../jarvis-avatar.js` cuida da cena,
do áudio e da montagem no botão original do Núcleo.

O glTF não leva os shaders de nós nem o pelo de geometry nodes do Blender: o exportador
deixou só uma textura plana de frente, e o chimpanzé parecia 2D. `jarvis-chimpanze.js`
refaz no navegador o material de `build_chimpanze_v2.py` (o script de origem do modelo): detalhe de três
projeções (`jarvis-chimpanze-frente/perfil/costas.png`) misturadas pelos pesos `pesos_proj`
(COLOR_1) e pelos mapas UV_frente/UV_perfil/UV_costas, borda, linhas de varredura, faixa que
percorre a cabeça (mais rápida pensando), desvanecer no pescoço, olhos HUD e dentes pelo
UV_olho, e cerca de quinze mil fios de pelo penteados para baixo e para trás. As cores são o azul
do Blender (CIANO e AZUL), não o tema, para ficar igual ao render; o brilho em volta (o bloom do Blender) é um
`drop-shadow` do canvas na cor do tema. A cabeça fica em três quartos e gira devagar.
Holograma de verdade (08/10/2026): a luz é somada, nunca escurece; a câmera aparece através.
A pele desenha só a superfície da frente, sobre uma passada de profundidade, então os dentes e
a nuca não vazam pelos lábios. Linhas de projetor na tela, tremulação, uma barra de
interferência que sobe devagar e falhas de sinal raras (frequentes na raiva). Os dentes são luz
com bordas, não blocos brancos, e só aparecem com a boca aberta.

Boca (08/10/2026): os dentes só existem com os lábios abertos (fala ou sorriso com dentes);
o focinho é quase sólido (a sombra fumê chega a 97% ali) e as rugas da foto no lábio, que
pareciam dentes, ficam suavizadas; o interior da boca é opaco e escuro, e uma elipse escura
atrás dos lábios (que some vista de lado) cobre as frestas dos cantos.

Olhos e dentes (08/10/2026): ao contrário do resto, são opacos; os olhos, uma lente azul-escura com a íris
acesa, o anel e a pupila escura por cima. Só luz somada, sumiam em fundo claro; assim a forma
deles se mantém em qualquer ambiente.

Pensando e ouvindo (08/10/2026): pensando (esperando o cérebro), o holograma pulsa cerca de
1,3 vez por segundo e faz a cara pensativa (olhos para cima e de lado, uma sobrancelha um pouco
erguida, lábios apertados, cabeça inclinada); ouvindo (esperando o usuário), fica atento e
pulsa devagar, como respiração.

Girar com a mão (08/10/2026): pegar o Zé com a pinça e segurar parado um segundo entra no
"modo giro" do Barehands, como nos modelos do Acervo; o giro vai para dentro da cena 3D
(o macaco vira de verdade, o cartão fica plano), com o embalo do gesto. Solto, ele volta a
olhar para a frente (a volta inteira mais próxima). `em3D` no stage.html decide quem gira por
dentro; `jarvisItemDe` entrega o item do anel ao avatar.

Jeito do Zé (08/10/2026): "dá uma voltinha" (comando local do Zé, ação `girar` do
controle, `jarvisAvatar.girar(voltas)`) gira uma volta completa e suave terminando de frente,
com cara alegre e uma frase variada. Girado demais pela mão (umas duas voltas e meia em
poucos segundos) ele fica tonto: olhos rodando, cabeça bamba, sinal falhando, verde de enjoo;
a página manda o evento `tonto` (`jarvisControle.evento`) e o Zé fala uma reclamação, no
máximo uma a cada vinte segundos.

Emoções: `alegria`, `duvida`, `raiva` e `tristeza` (e `neutro`). Usam as shape keys do arquivo, incluindo três
que `expressoes_blender.py` acrescenta como variações (a boca e as sobrancelhas medidas pelas
chaves Boca_Aberta, Erguida e Brava): `Sorriso` (cantos
da boca e bochechas), `Sobrancelha_Duvida` (uma sobe, a outra franze) e `Rosnar` (lábio de
cima e nariz), `Sobrancelha_Triste` (pontas de dentro sobem) `Boca_Triste` (cantos descem,
lábio de baixo avança) e `Sorriso_Dentes` (os lábios se afastam sem abrir a mandíbula e os
dentes aparecem; é o sorriso da alegria). A tristeza abaixa a cabeça, escurece o azul e respira devagar. A dúvida inclina a cabeça, a alegria levanta e balança mais, a raiva abaixa,
puxa o azul para o vermelho e falha o sinal. Vêm de `state/expressao.json` (pelo `/orb`; o
Zé escreve quando a resposta começa com `[alegria]`, `[duvida]` ou `[raiva]`), da ação
`expressao` do controle ou de `jarvisAvatar.sentir(nome, segundos)`.

Se o modelo no Blender mudar de nomes de material, UVs ou atributos, este arquivo precisa
acompanhar.

Para trocar o modelo: exportar do Blender em glTF binário, +Y para cima, com shape keys,
sem Draco, e substituir `jarvis-chimpanze.glb`. As shape keys usadas são `Boca_Aberta`
(voz), `Piscar`, `Olhar_Esq`/`Olhar_Dir`/`Olhar_Cima` (olhar), `Arregalar` e
`Sobrancelha_Erguida` (ouvindo) e `Semicerrar` (pensando, em repouso); as que faltarem são
ignoradas, mas `Boca_Aberta` é necessária para falar.

O robô anterior (`jarvis-robo.js`, `jarvis-robo.glb`) ficou no repositório, sem uso.

## Fala e movimento

A shape key `Boca_Aberta` é aberta pela amplitude do áudio que o Piper
está reproduzindo, recebida pelo contrato existente `/orb`. Uma pausa real no PCM fecha
a boca mesmo durante o estado `speaking`. Ouvir ou pensar nunca abre a boca.
É animação pela energia da voz, não alinhamento de visemas ou leitura de fonemas.

Movimentos pequenos da cabeça, olhar, piscar e halo são desligados com a preferência do sistema
por movimento reduzido; o movimento informativo da boca continua. Tema e humor tingem
os emissores. A legenda informa pronto, ouvindo, pensando ou falando.

O desenho fica limitado a cerca de trinta quadros por segundo e oitocentos e quarenta
pixels por lado. WebGL por software mantém o anel para não competir com o detector.
Falha de carga ou perda do contexto gráfico também restaura o anel. Trocas rápidas de
visual cancelam montagens pendentes; fechar o objeto libera geometrias e materiais.

## Verificação

`tests/test_avatar.py` exercita o estágio real com o chimpanzé: shape keys presentes, boca
aberta pela onda de fala, fechada no silêncio e ao ouvir, troca de visual, clique e pinça do
Núcleo, montagem concorrente e liberação da cena. WebGL por software (só nos testes) desenha
a cerca de dez quadros por segundo para não roubar CPU dos outros testes.

Em 08/10/2026, na janela instalada (Radeon 740M), com o material refeito e o pelo: cerca
de setenta mil triângulos, treze chamadas de desenho, trinta quadros por segundo, memória de
vídeo entre 420 e 455 de 512 MB; boca abrindo com a onda e fechando no silêncio.

Referência técnica: [three.js](https://threejs.org/docs/), versão já usada pelo front
fixada em 0.160.0. Código visual mantido neste repositório sob AGPL-3.0-or-later.
