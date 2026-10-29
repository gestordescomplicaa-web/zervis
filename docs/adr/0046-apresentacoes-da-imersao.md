# 0046 — As apresentações da Imersão: o Zé mostra os próprios dados em painéis holográficos

- Data: 29/10/2026
- Status: **Aceito como direção** (visual aprovado no laboratório do holograma; validação na
  máquina real em andamento).

## Contexto

A pessoa achava o holograma do Zé feio e queria a Imersão com cara de jogo: o Zé em holograma,
um fundo escuro animado opcional e, principalmente, o Zé se apresentando, indo para o canto e
mostrando dados em painéis holográficos. Pediu também que tudo o que ele mostra saia primeiro
do que ele sabe de si (ADR 0045), e que os gestos do Barehands não quebrem.

## Decisão

1. **O Zé é uma constelação de luz** (`avatar/jarvis-constelacao.js`): o mesmo modelo do Blender
   desenhado em pontos ligados aos vizinhos, com brilho, varredura, falhas, a montagem ao aparecer
   e um projetor embaixo. Só o desenho muda: a boca, as emoções, o giro e a tontura seguem a lógica
   de `jarvis-chimpanze.js`.
2. **Fundo opcional** (`jarvis-fundo.js`): a câmera ou o escuro animado, na tecla F e no menu. No
   escuro o vídeo só encolhe, e as mãos continuam sendo lidas. Opcional por causa dos óculos, que
   mostram o mundo real.
3. **Os painéis são cartões de verdade do quadro.** `jarvisStage.adicionar` os põe na mesma lista
   que a pinça percorre: a mão pega, move, amplia e arremessa um painel como qualquer cartão.
   Nenhuma linha do motor das mãos muda.
4. **Os dados vêm só do autoconhecimento.** O Zé grava `autoconhecimento.json` na pasta de estado
   uma vez por minuto (`Painel.autoconhecimento`), e a Imersão o entrega em `GET /autoconhecimento`,
   só com o token. A tela não lê outra fonte.
5. **Quem dispara:** a tecla A, o menu (Configurações → Apresentação) e a ação `apresentar` da tela
   (`quem` ou `encerrar`), que o cérebro usa em pedidos como "se apresenta".

## Consequências

- Os títulos da tela seguem a linguagem de produto (Identidade, Atividade, Conexões); a frase do
  Zé vai na legenda.
- A legenda é só texto por enquanto; o Zé falar cada passo com a própria voz fica para a etapa em
  que ele cria as apresentações a partir de pedidos (um catálogo de cenas preenchido por um modelo
  rápido), que terá o seu próprio ADR.
- Arquivo novo da página entra na lista do servidor dos testes (`tests/imersivo/test_brain_navigation.py`).
