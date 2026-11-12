# 0082 — Projetos 3D: a peça modelada por uma sessão, mostrada como sólido

- Data: 12/11/2026
- Status: **Aceita** (`tests/test_projetos3d.py`; a prévia sólida conferida com um STL real numa
  Imersão de teste). Imprimir fica para a próxima etapa.

## Contexto

Quem usa trabalha com impressão 3D e quer pedir ao Zé: "cria tal peça em 3D, mostra na Imersão
e, se estiver boa, imprime". A Imersão só mostrava modelos prontos, em holograma (ADR 0049); nada
gerava peça nem guardava os arquivos de um trabalho. Há dois tipos de pedido bem diferentes: a
peça funcional (suporte, caixa, encaixe), que precisa de medida exata, e a arte a partir de uma
imagem, que quem usa já faz com uma pipeline própria (imagem, contornos, relevo, Blender).

## Decisão

1. **Um projeto é uma pasta** em `<raiz dos projetos>/projetos-3d/<id>/`, ao lado dos outros
   projetos, com `projeto.json` (nome, tipo, pedido, a sessão) e os arquivos da peça. A aba
   **Projetos 3D** (grupo Trabalho) lista os projetos, os arquivos e as medidas de cada STL.
2. **Quem modela é uma sessão de código** (ADR 0068), criada junto com o projeto, com a primeira
   tarefa. O Zé escreve o `AGENTS.md` da pasta (e um `CLAUDE.md` que o importa): as entregas (um
   STL por peça, em milímetros, orientado para imprimir; o `gerar.py` com as medidas no topo; um
   `LEIA_ME.md`), as regras de impressão (a mesa da impressora, paredes, folgas, balanços) e o
   caminho de cada tipo:
   - **peça funcional:** modelagem paramétrica em Python (build123d ou CadQuery);
   - **arte a partir de imagem:** a imagem fica em `entrada/`, e a sessão segue a pipeline de arte
     de quem usa (a pasta vem dos ajustes da aba; sem ela, OpenCV, shapely e manifold3d).
   O Blender entra em linha de comando, quando existe na máquina. Nada é impresso pela sessão.
3. **A peça aparece como sólido na Imersão.** O Zé lê o STL (binário ou texto), mede o tamanho, o
   volume e se a malha é fechada (cada aresta de exatamente dois triângulos), e o converte num GLB
   fosco, cor de mármore, dentro do Acervo (`3d/projetos/<id>/`), que é o que a Imersão serve. A
   Imersão já tinha o modo sólido, com luz de ambiente; `mostrar_modelo` passa a aceitar
   `estilo: solido`. Uma peça achatada (um relevo, que se imprime deitado) aparece de frente; uma
   alta, de pé. A prévia só é refeita quando o arquivo muda.
4. **Pela voz:** `projeto3d_criar` (pede o sim falado, como criar uma sessão),
   `projetos3d_listar` e `projeto3d_mostrar` (livres: só leem e mexem na própria tela).
5. **Os ajustes são de quem usa** (`<config>/projetos3d.json`): o nome da impressora, a mesa em
   mm e a pasta da pipeline de arte. Nada disso vai para o código.

## Consequências

- O trabalho de modelar gasta a conta do agente da sessão, como qualquer sessão.
- Sem o Blender ou sem a pipeline de arte, a sessão segue com as bibliotecas de Python.
- Imprimir (fatiar com o Bambu Studio por linha de comando, mandar pela rede local e acompanhar)
  é a próxima etapa, sempre com o sim falado; depende do modo de desenvolvedor da impressora.
