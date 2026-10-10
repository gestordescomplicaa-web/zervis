# Desempenho do front — primeira melhoria, 08/10/2026

Pedido: reduzir os engasgos ao usar pinças com vários orbes e abas abertos.

## Mudanças

- A prévia mantém seus elementos enquanto o conteúdo permanece igual. Dados novos
  continuam aparecendo; o tamanho é invalidado ao reabrir, trocar conteúdo ou pelo
  ResizeObserver quando a caixa muda de tamanho.
- Conexões mantêm seus caminhos SVG. Só atributos alterados são escritos; fechar
  orbes ou o mapa remove suas linhas. Todas as posições são lidas antes das escritas.
- A física lê as dimensões dos cartões juntas, antes de escrever as animações.
- O canvas do anel deixa de desenhar atrás do avatar. A amplitude da fala continua
  sendo calculada para a boca, e o desenho retorna ao selecionar o anel.

## Comparação na máquina

Chromium isolado com a Radeon 740M real (ANGLE/radeonsi), janela 1906 por 1036,
avatar atual do Zé, cinco orbes e três listas. Mesma rotina do diagnóstico anterior:
um segundo e meio para acomodar cada cena e quatro segundos medidos. Rodada antes
das alterações e rodada depois, sem testes concorrentes. Cenas acumulativas; o
apontar usa o controlador real com amostras sintéticas sobre o mesmo nó. Sem
MediaPipe, câmera ou modelos adicionais do Acervo. Não mede latência da mão real.

| Cena | Trabalho da thread antes/depois | Layout antes/depois | Recálculos antes/depois |
|---|---|---|---|
| anel | 292.3 / 259.0 ms | 12.7 / 1.0 ms | 123 / 3 |
| avatar | 398.3 / 302.1 ms | 13.1 / 0.6 ms | 123 / 2 |
| cinco_orbes | 448.8 / 312.7 ms | 15.5 / 0.7 ms | 123 / 3 |
| tres_listas | 390.0 / 312.7 ms | 15.8 / 0.9 ms | 124 / 3 |
| mapa | 709.3 / 524.3 ms | 32.8 / 12.0 ms | 249 / 136 |
| mapa_apontando | 921.9 / 509.1 ms | 83.0 / 11.4 ms | 488 / 128 |
| trabalho | 457.1 / 322.2 ms | 19.2 / 2.4 ms | 128 / 9 |

No Mapa apontando, o trabalho da thread caiu cerca de 45% e o tempo de layout,
86%. São tempos acumulados em quatro segundos, não atraso por gesto. Ambas as
versões ficaram próximas de 60 FPS neste ensaio. Uma rodada por versão: variação
entre execuções e outros processos não foi isolada estatisticamente.

As regressões do navegador verificam reuso das linhas enquanto o anel se move,
reuso e troca segura do conteúdo da prévia, suspensão e retorno do canvas plano,
além da fala e dos gestos já cobertos na suíte. O ganho com mão física continua
pendente do teste do usuário. O rastreador ainda é síncrono na thread da interface.

A janela diária estava fechada durante a alteração. O servidor usa os arquivos do
repositório; abrir novamente a janela carrega esta versão. Não houve reinício do
núcleo, ajuste da câmera ou alteração da calibração.

## Verificações

O roteiro de navegação do Mapa estava fora da descoberta do pytest. Agora entra no
`make check`, com o índice do Guia corrigido para o manifesto atual. Suas 32
verificações passaram em execução direta, sem erros de JavaScript. Incluem os
novos casos de desempenho e pinça, arraste, ampliação, perda de rastreamento,
retração dos orbes e janela pequena. A suíte completa passa pelo gancho do commit.
O servidor instalado também foi consultado: HTML e JavaScript servidos são
idênticos aos arquivos alterados.

## Ergonomia de gestos — 09/10/2026

O usuário confirmou uma grande melhoria com a primeira otimização. A rodada seguinte
prioriza acertar controles e ampliar a leitura, sem trocar linguagem ou rastreador.
O mouse permanece: ações por evento, sem outro ciclo de renderização.

Comparação de observação com o ensaio isolado anterior (quatro segundos por cena,
Radeon 740M, sem MediaPipe; uma rodada por versão, sem atribuição causal estatística):

| Cena | Trabalho anterior / atual | Layout anterior / atual | FPS atual |
|---|---|---|---|
| Três listas | 312,7 / 290,1 ms | 0,9 / 0,8 ms | 60,0 |
| Mapa | 524,3 / 529,4 ms | 12,0 / 11,4 ms | 60,0 |
| Mapa apontando | 509,1 / 533,9 ms | 11,4 / 11,1 ms | 60,2 |
| Trabalho | 322,2 / 288,6 ms | 2,4 / 2,3 ms | 60,1 |

Não há indicação de regressão relevante nessas cenas; não se promete ganho novo de
FPS. Zoom contínuo de texto exige layout e não foi cronometrado nesse ensaio. A
sensação da mão real deve ser conferida na câmera, principalmente com várias abas.
A inferência síncrona continua candidata a uma etapa futura se os engasgos voltarem.

O novo módulo de painéis não cria timers, observadores ou renderizadores. O seletor
de alvo acompanha a ordem visual. Os testes antigos de configurações foram adaptados
para rolar até as opções maiores antes de pinçar; a verificação do pulso do avatar
aguarda a mesma variação mínima por até oito segundos, evitando depender de oito
amostras fixas sob renderização por software concorrente.
