# 0052 — Objetos 3D: modelos oficiais da NASA e escolha olhando a prévia

- Data: 02/11/2026
- Status: **Em validação** (conferido com o cérebro de verdade; falta a Imersão real).

## Contexto

Os objetos 3D saíam feios (ADR 0049). A causa estava na fonte: o 3DAssets.dev tem quase só
modelos feitos por IA, muitos low-poly (o cavalo tinha 704 triângulos), e o Zé escolhia pelo
título, sem ver nada. Uma busca por "coração humano" trazia uma sala e uma floresta. A pessoa quer
só fontes gratuitas para qualquer uso: o Poly Pizza ficou de fora porque cobra no uso comercial.

## Decisão

1. **Modelos oficiais da NASA**, de domínio público e sem chave: os 257 `.glb` do repositório
   `nasa/NASA-3D-Resources` (Hubble, ISS, Saturn V, ônibus espacial, Perseverance, James Webb,
   Voyager, astronauta e outros). O índice vem da API do GitHub e fica uma semana no Acervo; o
   download só aceita esse repositório. Quando o nome tem todas as palavras da busca, só a NASA
   volta.
2. **Qualidade em cada achado:** oficial, detalhado, médio ou simples (por triângulos), e se foi
   feito por IA; o simples e o feito por IA vão para o fim.
3. **O Zé olha antes de escolher.** A busca devolve a prévia de cada achado como imagem (o Claude e
   o Codex enxergam), até 200 kB cada e 450 kB no total: o canal com o SDK do Claude aceita 1 MB por
   mensagem, e uma prévia grande da NASA derrubou a conversa no teste. Sem um bom, ele diz que não
   achou em vez de mostrar um feio.
4. **A Imersão abre Draco e meshopt** (os decodificadores da mesma versão do three.js): quase todos
   os modelos da NASA vêm em Draco. KTX2 continua recusado.
5. **Nada de pensar em voz alta:** tudo o que o modelo escreve, inclusive entre ferramentas, é
   falado na hora. A persona e a descrição da busca dizem isso; no teste, o cérebro comentava em
   inglês a comparação das prévias.

## Teste com o cérebro de verdade (02/11/2026)

Claude Opus 5.5: Hubble, Estação Espacial, Saturn V e astronauta viraram os modelos oficiais da
NASA, de 7 a 15 s; cavalo e coração humano ele recusou, dizendo que só havia modelos feitos por IA
e toscos, e ofereceu o melhorzinho ou um holograma de peças. O Hubble em Draco abriu com textura no
navegador. Cada pedido gastou de 75 a 90 mil tokens.

## Consequências

- Objetos comuns (animais, carros, órgãos) continuam sem fonte boa e gratuita sem cadastro. O
  próximo passo seria o Sketchfab (conta gratuita e chave; modelos CC0 e CC BY).
- A busca agora lê o GitHub; sem rede, a NASA falha e a outra fonte segue.
