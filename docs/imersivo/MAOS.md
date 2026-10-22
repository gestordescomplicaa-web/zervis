# Zé — calibrador das mãos, câmera e luz

Arquivos: `jarvis-maos.js` (página), `jarvis_maos.py` (servidor), ganchos em
`stage.html` e `jarvis-cerebro.js`. Testes: `tests/test_maos.py`.

## O original é sempre o caminho de volta

- `PADRAO` (em `jarvis-maos.js`) é a afinação original do `stage.html`. Não é gravado
  em lugar nenhum; sem perfil, com perfil inválido ou fora dos limites, vale ele.
- O perfil calibrado fica em `state/maos-perfil.json`; cada gravação guarda o anterior
  em `state/maos-perfil.anterior.json`.
- Os controles originais da câmera são salvos uma única vez em
  `state/camera-original.json` (nunca sobrescrito) antes da primeira mudança.
- **Voltar ao padrão** (Shift+K, botão no calibrador ou “volta as mãos ao padrão” por
  voz) apaga o perfil, restaura a câmera e desliga a luz automática.
- Se a página parar (sem batimento por vinte segundos) ou o servidor sair, a câmera
  volta sozinha aos valores originais.

## Calibração guiada (K, o chip ✋ MÃOS ou “calibrar as mãos”)

1. Câmera e luz (dois segundos).
2. Mão aberta parada: mede o tremor natural.
3. Cinco pinças rápidas no círculo, do jeito da pessoa: abertura dos dedos, formato
   de OK, quanto o cursor anda e quanto dura uma pinça.
4. Três vezes quase encostando, sem encostar.
5. Três vezes a mão fechada: o punho que nunca pode virar pinça.

**Encostar de verdade (toque3).** A abertura da pinça original é medida só na imagem:
um dedo NA FRENTE do outro aparece sobreposto e conta como encostado. A calibração mede
a mesma distância em 3D (o MediaPipe dá a profundidade de cada ponto) nos toques e no
"quase", e põe a linha mais perto do toque (40 % do caminho). Se o "quase" ainda passar,
a linha desce até o limite dos toques medidos. 0 = desligado (o original); perfis
antigos continuam válidos e ganham isso ao recalibrar.

A calibração só alivia o original (abertura da pinça, formato de OK e arco nunca ficam
mais exigentes). Se um punho passar, aperta primeiro a abertura até o que a pinça medida
precisa e só depois o formato. O tremor usa o percentil setenta e cinco da mão parada.
O perfil novo só é aceito se reconhecer pelo menos tantas pinças quanto o atual e o
original, no mínimo oitenta por cento delas, e rejeitar todos os punhos. Senão, nada muda.
Durante a calibração, a mão não move nem abre nada.

Parâmetros e limites: abertura da pinça frontal (0,22–0,40) e de perfil (0,30–0,42),
contraste do OK (0,08–0,28), arco dos outros dedos (1,15–1,40), soltar (0,45–0,65;
rápido 0,60–0,85), tremor em px (12–48), mão fantasma em px/s (700–1800) e tempo de
uma pinça em ms (300–900).

## Aperfeiçoamento no uso

Cada pinça no cérebro e no anel/círculos registra o resultado (abriu, moveu, demorou,
fantasma, prova, fora do alvo, sem alvo). Uma pinça que quase abriu e foi repetida logo
no mesmo lugar com sucesso é evidência; três evidências do mesmo tipo alargam um passo
(tremor +3 px, tempo +60 ms, fantasma +100 px/s), no máximo um ajuste a cada dois
minutos e sempre dentro dos limites. O diagnóstico vai para `state/maos-diagnostico.json`
a cada trinta segundos, quando há novidade, incluindo pinças recusadas pelo formato.

No cérebro, o alvo fica travado quando a pinça fecha: soltar sobre ele ou dentro da
tolerância ainda abre. A velocidade de mão fantasma passa a olhar só os últimos 120 ms.

## Câmera

`?fps=auto` (padrão da janela) pede 60 quadros e mede o que chega: se a inferência
passar de 14 ms por quadro, volta para 30, e tenta 60 de novo depois de um minuto
calmo (abaixo de 10 ms), esperando o dobro a cada nova tentativa. A resolução segue `?res=` (720p basta: o
MediaPipe trabalha com um recorte pequeno da mão).

## Luz

A luz automática ajusta a própria câmera (via `v4l2-ctl`): exposição manual curta
(no máximo 80 % do tempo de um quadro, 13 ms a 60 qps) para a mão não borrar, e o
ganho compensa a luz. **Ajusta e trava:** acerta o nível em passos amortecidos
(um a cada 0,9 s, esperando a câmera mostrar o efeito) e fica fixo. Só volta a ajustar
se o brilho médio da imagem ficar fora da faixa larga (0,30–0,68) por cinco segundos
seguidos, ou ao calibrar. Mede a imagem inteira suavizada, para a mão entrando e saindo
não mexer na luz (correção do usuário: o brilho oscilava).
Brilho, contraste e gama vão aos valores de fábrica. Só se a câmera chegar ao limite
de ganho num ambiente escuro, a imagem entregue ao rastreador recebe um reforço
de brilho por software (até 2×), também mostrado na tela.

## Brilho da câmera (filtro que se liga)

Chip **☀ BRILHO** no HUD (pinça ou clique), tecla B (Shift+B volta um nível) ou voz
("liga / aumenta / diminui / desliga o brilho da câmera"). Quatro níveis: desligado,
suave, médio e forte. Cada nível pede mais luz à própria câmera (alvo de brilho 0,48,
0,54, 0,60 e 0,66: obturador mais longo dentro do tempo do quadro, depois ganho) e
aplica um filtro leve na imagem mostrada (brilho 1,1 / 1,2 / 1,35, com um pouco de
contraste e saturação). A medição dá mais peso ao centro da imagem, onde está a pessoa,
do que a uma janela clara ao fundo. Fica guardado na janela.

## Cores do Zé

`jarvis-tema.css` e `jarvis-tema.js`. Cinco temas: original, roxo, marinho, esmeralda e
grafite. Menu D, tecla T (passa para o próximo) ou voz ("tema roxo", "tema azul marinho",
"tema verde", "tema grafite", "tema original"). Cada tema novo é só um bloco de variáveis
no CSS mais as cores do anel e do grafo no JS; trocar não pesa (uma classe na página, um
redesenho). O original é exatamente o CSS do Barehands; o roxo existe para telas
claras e replica o original (vidro transparente, mesmos brilhos e layout) num violeta
mais escuro e um degrau mais denso, para manter o contraste num ambiente muito claro. As cores do Zé (cérebro, HUD, calibrador)
vêm de variáveis `--jv-*`; o anel (canvas) e o grafo (SVG) são recoloridos pelo script.

## Menu de configurações (tecla D)

`jarvis-config.js`. Barra lateral à esquerda (onde ficava a leitura do D), no mesmo vidro
do quadro; fica dentro do `#hint` para os chips de cérebro e de consumo manterem o estilo
do HUD. A frente mostra só o anel e a linha CPU · RAM · GPU · VRAM; o menu
reúne mãos (estado, calibrar, voltar ao padrão), brilho da câmera, cores, as baterias dos
cérebros e o consumo de tokens. Funciona com pinça, mouse e teclado; Esc fecha; Shift+D
mantém a leitura de depuração. Por voz: "abre as configurações".

## O Zé na própria tela

`jarvis-controle.js` e, no serviço do Zé, `jarvis/rosto/tela.py` com as ferramentas `tela_ver` e
`tela_agir`. O Zé escreve uma lista de ações em `state/tela-comando.json`; a página as
executa em ordem, com as mesmas animações da mão (meio segundo entre passos) e responde em
`state/tela-estado.json` (POST `/tela/estado`). O estado também é renovado a cada cinco
segundos: cérebro aberto e modo, item em foco, zoom, áreas e itens por nome e id, menu,
tema, brilho, mãos e se a janela está visível.

Ações: abrir/fechar o cérebro, modo (cérebro, trabalho, foco), focar (área ou item pelo nome,
sem acento nem maiúscula), localizar, zoom, enquadrar, mover, rolar, voltar, aguardar (para
passeios), menu, tema, brilho, calibrar as mãos e voltar ao padrão. Um passo inválido volta
como erro claro e os outros continuam; cada comando roda uma vez; comando com mais de 30 s
não é repetido. Antes de mostrar, o Zé traz a janela para a frente pelo Hyprland
(escondida, o Chromium pausa as animações). Aberto pelo Zé, o cérebro fecha sozinho
90 s depois do último passo; aberto à mão, fica.

## O Núcleo: o Zé se reconhece na interface (07/10/2026)

O **Núcleo** (nome escolhido pelo autor) é o anel do Zé com os orbes que nascem dele:
Cérebro, Guia, Memória e Acervo. A janela do Zé é onde ele vive (câmera, HUD, menu D).
`window.jarvisStage` ganhou `nucleo()`, `abrirNucleo()`, `fecharNucleo()`, `abrir(nome)` e
`fechar(nome)`: um orbe pelo título ou uma nota pelo nome, sem acento nem caixa e pela raiz da
palavra ("começar" acha "Comece aqui"); `fechar("tudo")` fecha painéis, notas, cérebro e orbes.
O controle expõe isso como as ações `nucleo`, `abrir` e `fechar`, e o estado publica `nucleo`
(aberto, orbes, orbes e notas abertos).

Comandos locais (sem o cérebro): "abre o núcleo" (mostra os orbes), "fecha o núcleo" (recolhe),
"abre o guia (do núcleo)", "abre o acervo", "abre a memória do núcleo", "fecha o guia", "fecha a
janela do Zé" ou "desliga a câmera", "fecha seu cérebro", "mostra os projetos / agentes /
tarefas / conexões / memórias". "Aumenta o brilho" sem dizer de quê é o brilho da câmera só
quando a janela do Zé é a ativa; fora dela, segue para o cérebro (monitor).

Rapidez: a página consulta comandos a cada 150 ms, confirma o início (`recebido`) e passeios
voltam ao Zé na hora, seguindo na tela enquanto ele fala; ações rápidas (tema, brilho, menu)
têm 120 ms entre passos. Mãos primeiro: com uma pinça nos últimos 1,5 s, a ação espera a mão
descansar (até 6 s); o estado publica `maos_em_uso`.

## Teclado (07/10/2026)

`jarvis-teclado.js`: um ícone de teclado ao lado de CPU · RAM · GPU · VRAM (em `#hud-m`; os
medidores ficam em `#hud-med`, com `display:contents`, para o ícone sobreviver à atualização)
abre uma barra de texto. Enter envia por `POST /teclado` (só JSON), que grava
`state/teclado.json`; o Zé lê como fala autorizada e responde em `teclado-resposta.json`,
mostrado embaixo da barra conforme é falado. ↑/↓ recuperam os últimos 20, Esc fecha, "/" abre.
Digitar nunca dispara atalhos (R, D, C, P, K, B, T): os atalhos ignoram campos de texto. A
pinça também abre o ícone e aperta os botões da barra. Ação `teclado` no controle.

## Orbes organizados (07/10/2026)

O `barehands.json` é o manifesto do Núcleo: cada orbe tem `id`, `title`, `kind` (brain = Mapa,
notes, media = Acervo, orca), `apelidos` falados e `descricao`; `/config` entrega tudo menos as
pastas. Orbes: Mapa (era Cérebro), Guia, Identidade (era Memória), Acervo e Orca (novo, lê
`/jarvis/rotina`: Projetos, Agentes, Tarefas; um item abre no Foco do Mapa). Um catálogo único
dá a cada item um endereço (orbe/pasta/item) e um nome falado limpo (`burrinho` para
`burrinho_refeito_final.glb`); `jarvisStage.abrir(nome, orbe)`, `buscar(nome, orbe)` e
`fechar(nome)` usam esse catálogo, e o controle expõe `abrir`, `buscar` e `fechar` com `orbe`.
O Mapa ganhou nomes do glossário: vistas Geral, Trabalho e Foco, Zé no centro.

## Avatar (07/10/2026)

`jarvis-avatar.js`: um busto holográfico no lugar do desenho do anel, dentro do próprio widget
do anel (tocar continua abrindo os orbes, a pinça arrasta, os cabos ligam). Rosto: escaneamento
de Lee Perry-Smith (CC BY 3.0, `avatar/`), com as costuras soldadas, a barba suavizada e uma
passada de profundidade antes da cor (só a superfície mais próxima aparece). Crânio, pescoço,
gola, ombros e cinco painéis curvos com dados reais (projetos, agentes, sistema, tarefas,
aprendizado) são gerados. Fala: a amplitude do anel abre a mandíbula; estado, tema e humor dão
a cor. Desenha a ~30 qps e para com a janela escondida. Com WebGL por software o anel fica
(`?avatar=forcar` força, para os testes). Menu D "Visual: Avatar / Anel", ação `visual` no
controle, "mostra o avatar" / "volta o anel" por voz; lembrado por janela.
