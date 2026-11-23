# 0117 — A paleta dos vídeos: estável, e tirada de um site

- Data: 23/11/2026
- Status: **Aceito** (pedido de quem usa, 19/11/2026).
- Segue o Editorial na paleta da marca ([ADR 0115](0115-copy-manda-na-tela.md)).

## Contexto

Quem usa aprovou a base dos vídeos, mas pediu uma paleta mais estável (a tela virava inteira para
a cor da marca várias vezes) e a escolha da paleta a partir de um site: colar um endereço e o Zé
montar as cores sozinho.

## Decisão

1. **Paleta de um site** (`zervis/video/paleta.py`): o Zé abre o site com a captura da Imersão (só
   HTTPS, atrás da trava de rede, ADR 0058), reduz o print às cores principais sem fazer média (as
   parecidas se juntam e vale a mais frequente, para a cor sair exata) e escolhe: o fundo (a que
   mais ocupa), o texto (a de mais contraste; preto ou branco se nenhuma lê bem) e dois destaques
   (as mais vivas que aparecem de verdade, nunca a cor do texto; o segundo com outro tom). O print
   não fica guardado. A escolha vale para todos os vídeos até voltar às cores da marca.
2. **Tinta e papel:** além das seis cores, o vídeo recebe a mais escura e a mais clara da paleta;
   o Editorial escreve com a tinta sobre o papel, seja o site de fundo claro ou escuro.
3. **Paleta estável:** a tela inteira na cor (fundo "cor" ou a frase "cheia") no máximo uma vez
   fora do fecho; o plano troca o excesso pelo fundo claro, e o diretor é avisado disso.
4. **No painel:** o cartão Vídeos tem o campo Paleta (o endereço), "Usar cores do site", "Usar
   cores da marca" e as amostras da paleta em uso.

## Consequências

- Nada vem do modelo: as cores são as do site como ele aparece.
- Um site com foto grande no topo pode ter o fundo tirado da foto; aí basta tentar outra página
  ou voltar às cores da marca.
