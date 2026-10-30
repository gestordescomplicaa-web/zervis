# 0048 — Hologramas 3D de verdade, montados com peças

- Data: 30/10/2026
- Status: **Em validação** (o visual foi conferido no navegador de teste; falta a Imersão real).

## Contexto

As cenas do ADR 0047 têm o bloco `forma3d`, mas ele é uma nuvem de pontos girando num canvas 2D,
com nove formas fixas. A pessoa pediu "3D de verdade": o Zé cria o objeto na hora, e ela o trava
com a pinça e o vê de todos os lados. O Barehands já tem isso para arquivos `.glb` do Acervo: um
cartão de modelo com cena three.js própria, o vidro holográfico (borda acesa, raio de varredura,
brilho), a pinça que gira em todos os eixos e as duas mãos que ampliam.

## Decisão

1. **O Zé descreve, a página monta.** O bloco `holograma` traz `pecas`: esfera, cubo/caixa,
   cilindro, cone, pirâmide, toro, anel, cápsula, hélice, tubo e linha por pontos, ligação entre
   dois pontos e partículas. Cada peça tem posição, tamanho, giro, cor, rótulo e animação (girar,
   pulsar, flutuar, orbitar) e `filhos` que andam com ela (a Lua na Terra). `jarvis-holograma.js`
   limpa a receita (até 80 peças, dois níveis de filhos, números limitados) e a transforma em
   three.js. Nada da receita roda como código.
2. **O mesmo cartão do Barehands.** `buildModelScene` aceita a receita no lugar do `.glb`; o vidro
   holográfico guarda a cor de cada peça, com o raio de varredura compartilhado, e a animação roda
   a cada quadro. A pinça, o giro, o zoom e o "explodir" não mudam. `jarvisStage.holograma` põe o
   cartão no quadro; nas cenas, ele fica preso ao feixe do Zé e sai com "tira a animação".
3. **A ligação se orienta sozinha.** Para moléculas e estruturas, `ligacao` recebe `de` e `ate`:
   pedir um ângulo de cilindro ao modelo dava ligações tortas.
4. **O enquadramento mede só os sólidos.** Estrelas, rótulos e trilhas não encolhem o objeto, e o
   cartão começa visto um pouco de cima, para órbitas e anéis lerem como círculos.
5. **O esquema leva todas as peças por extenso**, sem `$ref`, que nem todo cliente de ferramentas
   resolve; o modelo só preenche o que o esquema lista (ADR 0047).

## Teste com o cérebro de verdade (30/10/2026)

Claude Opus 5.5, ferramentas simuladas, 8 pedidos de 3D (sistema solar, átomo de carbono, CO₂,
foguete, DNA, casa, rede neural, carro): os 8 viraram hologramas montados com peças, de 18 a 41 s
e uns 50 mil tokens cada. O foguete veio com ogiva, aletas, motor e chama de partículas; o DNA, com
as duas fitas e 21 pares; a rede neural, com 13 nós e 36 ligações.

## Consequências

- O esquema de `tela_explicar` passou de uns 4 para uns 8 mil caracteres por chamada.
- Cada holograma é um contexto WebGL a mais; a página põe no máximo quatro blocos por página.
- O laço substituto dos testes de navegador não desenhava os modelos 3D; agora desenha.
- Próximos passos possíveis: uma biblioteca de modelos prontos (NASA, Kenney) e, para o que ela
  não tiver, geração por IA, com o resultado guardado no Acervo.
