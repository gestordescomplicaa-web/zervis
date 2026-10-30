# 0049 — Modelos 3D prontos e livres, baixados para o Acervo

- Data: 30/10/2026
- Status: **Em validação** (conferido no navegador de teste; falta a Imersão real).

## Contexto

Os hologramas montados com peças (ADR 0048) servem para esquemas, mas um cavalo de esferas e
cilindros não se reconhece. Pedido "mostra um cavalo em 3D", o Zé chegou a achar um modelo livre
na internet e disse que não conseguia baixar. Ele anotou como melhoria "pesquisar, tirar print,
renderizar e exibir": isso daria uma silhueta 2D, não um objeto para girar com a pinça.

## Decisão

1. **Buscar e baixar de um acervo livre.** `modelo3d_buscar` consulta o 3DAssets.dev (CC0, busca
   e download sem chave) e devolve título, resumo, licença, triângulos e se foi feito por IA;
   `modelo3d_baixar` guarda o escolhido em `Acervo/3d/baixados/` e, com `mostrar`, já o põe na
   tela. Um modelo já baixado é reusado.
2. **Travas do download** (`zervis/imersivo/modelos3d.py`): só HTTPS e só os domínios da fonte,
   conferidos também em cada redirecionamento; até 40 MB; só `.glb` versão 2, inteiro em si (sem
   arquivo externo) e com malha; sem Draco, meshopt ou KTX2, que o carregador da Imersão não lê.
   A busca já tira esses modelos. Ao lado de cada arquivo, um `.json` guarda fonte, página,
   licença e autor, para o crédito quando a licença pedir.
3. **Livres de aprovação**, como as outras da tela: só leem uma fonte permitida e só gravam no
   próprio Acervo.
4. **Na tela, o mesmo cartão de modelo**, no vidro holográfico, mantendo as cores do modelo
   quando elas são cores (não branco nem cinza), para o que o Zé descreve continuar verdade. A
   ação `mostrar_modelo` e o bloco `modelo` das cenas aceitam só caminhos dentro do Acervo.
5. **A persona separa os casos:** objeto real é modelo pronto; esquema ou conceito (sistema
   solar, átomo) é holograma montado com peças.

## Teste com o cérebro de verdade (30/10/2026)

Claude Opus 5.5, com a busca e o download reais para um Acervo de teste: cavalo, avião, carro
esportivo e coração humano viraram busca e download (de 9 a 11 s, uns 75 mil tokens); o sistema
solar continuou montado com peças; "me explica como um cavalo galopa, com o modelo na tela" baixou
o cavalo e montou a cena com ele ao lado das etapas.

## Consequências

- A qualidade depende do acervo: há modelos simples e alguns feitos por IA (a busca diz quais).
- A primeira busca sai da máquina para o 3DAssets.dev; o Poly Pizza (mais de 10 mil modelos)
  pode entrar como segunda fonte quando a pessoa colar a chave gratuita dele.
- Silhueta 2D a partir de imagem e mapas de dados abertos (IBGE) ficam para depois.
