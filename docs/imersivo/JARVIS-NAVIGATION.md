# JARVIS — Geral, Trabalho e Foco

Atualização de 09/10/2026. A interface mantém o avatar e os círculos do Núcleo.
Código visual AGPL permanece neste repositório; o núcleo fornece JSON.

## Interação com as mãos

| Área | Pinça curta | Pinça e arraste | Duas pinças |
|---|---|---|---|
| Avatar e orbes | Abre ou recolhe | Move o avatar | Amplia o avatar |
| Grafo Geral | Abre o ponto ou expande a área | Puxa o ponto; fundo move o mapa | Ampliam o mapa; na mesma esfera, ampliam a esfera |
| Trabalho e Foco | Aciona o botão inteiro | Rola o conteúdo | Ampliam ou reduzem a leitura, entre 100% e 200% |
| Lista de uma orbe ou nota | Abre a linha; botões ajustam ou fecham | Título move; conteúdo rola | Ampliam a aba, com controles mantidos dentro da tela |
| Configurações | Aciona a opção | Rola a barra lateral | Sem ação de zoom |

As barras de tamanho ficam visíveis no Geral, Trabalho e Foco. **−**, **+** e
**Ajustar** também aceitam uma mão ou mouse. Cada vista de leitura guarda seu próprio
zoom. **↔**, ao lado de fechar, alterna o quadro entre a posição junto ao avatar e
uma área maior, reservando espaço para o HUD.

Nas listas e notas, o título é somente uma alça. Pinçar o título rapidamente não
fecha mais a aba: use **×**. Controles dessas abas medem pelo menos 64 pixels antes
da escala; o limite inferior de 85% mantém aproximadamente 54 pixels para acertar.
Ao ampliar, a caixa se adapta ao espaço da janela e o conteúdo continua rolável.
Novas orbes de notas, mídia e Orca usam os mesmos controles de lista.

Botões do Mapa, Foco, Trabalho, teclado e configurações têm alvos de pelo menos
56 pixels no tamanho normal. Os rótulos dos pontos também são clicáveis; as esferas
mantêm uma área de acerto maior durante o zoom. Painéis sobrepostos respeitam a
ordem visual depois de arrastar uma aba à frente.

Uma interação com duas mãos não dispara o botão usado como apoio. Perder o
rastreamento cancela a ativação. Atualizações do Foco esperam a pinça terminar antes
de substituir seus botões, preservando a posição de leitura.

## Mouse e teclado

- Clique usa as mesmas ações dos gestos. Nas listas, a linha inteira abre o item.
- Arrastar o título move listas, notas e o quadro do Mapa.
- Roda do mouse rola a leitura; **Ctrl + roda** amplia. No grafo, a roda amplia.
- Tab e Enter/Espaço percorrem e acionam os controles e as linhas das listas.
- Escape volta do Foco ou fecha o Mapa, conforme a vista.

O mouse foi mantido: os novos ouvintes só executam durante eventos; não há um novo
laço de animação ou rastreamento. O clique dos modelos do Acervo foi corrigido para
fechar o modelo, acompanhando a pinça curta, em vez de chamar o menu do avatar.

## Dados e validação

Memória e relações vêm de `/jarvis/mapa`; projetos e agentes, de `/jarvis/rotina`;
o quadro de frentes e próximos passos, de `/jarvis/foco`. O Foco mantém suas ações
explícitas, como marcar um passo e concluir uma frente. Números informativos não
viram ações novas. Pessoas e oportunidades continuam dependendo de fonte integrada.

`tests/test_interacao.py` acrescenta 27 verificações no Chromium: zoom com duas mãos,
rolagem sem ativação, atualização por voz durante a pinça, alvos, aba nova pelo
manifesto, mouse real via CDP, sobreposição, cancelamento e janela pequena. O roteiro
do grafo e as suítes de Foco, avatar, mãos, teclado e controle também entram no
`make check`. Os gestos desses testes são sintéticos; o aceite físico cabe ao uso.

Medições e limites de desempenho em [DESEMPENHO.md](DESEMPENHO.md).
