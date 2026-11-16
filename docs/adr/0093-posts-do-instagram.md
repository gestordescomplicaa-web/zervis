# 0093 — Posts do Instagram: o Zé cria o carrossel com a marca, e publicar é sempre com aprovação

- Data: 13/11/2026
- Status: **Em validação**: o texto e os slides foram feitos de verdade (o modelo e o Chromium,
  a partir de um artigo do blog); a publicação foi testada com a API da Meta simulada. Falta o
  primeiro post publicado.

## Contexto

O ADR 0057 deixou o Instagram só leitura, e disse que escrever nele seria outra decisão. Quem usa
quer que o Zé crie as postagens, que ele as veja e aprove, e que o Zé publique. O token do Login
do Instagram que ele já conectou tem a permissão de publicar (a cota respondeu 0 de 100 por dia), a
conta é Business e o Zé tem um endereço fixo na internet pelo túnel.

## Decisão

1. **Em Marketing, não em Redes sociais.** Criar e publicar é marketing; Redes sociais continua
   conversa e análise (WhatsApp, as métricas do Instagram, os avisos).
2. **O carrossel** (`zervis/marketing_posts.py`): o modelo (Sonnet, pela assinatura) escreve de 3 a
   7 slides, a chamada do último e a legenda, a partir de um tema ou de um artigo do blog e na
   linha do manual do site. A resposta é conferida e cortada nos limites.
3. **A cara da marca** (`zervis/marca.py`): o site declara no `zervis.json` o nome, o @, o logo, as
   cores e as fontes; a paleta pode ser trocada em Marketing ("Cores do site" ou "Paleta própria").
   Sem declaração, vale uma paleta neutra. Nada de uma marca em particular no código.
4. **Os slides** saem de um modelo HTML (capa, ideias numeradas, oferta com a chamada), renderizado
   pelo Chromium sem tela em 1080 x 1350 e salvo em JPEG, o único formato de imagem que a API
   aceita. Todo texto do modelo é escapado.
5. **Publicar só com aprovação**: "Publicar no Instagram" e "Confirmar publicação" no painel, ou
   `marketing_post_publicar` pela voz, que pede o sim. Nada sai sozinho, nem de uma automação.
6. **A Meta busca as imagens por um link público temporário** (`zervis/portal/publico.py`): um
   segredo de 32 bytes, só para os slides daquele post, por até 15 minutos, fechado logo depois.
   A rota `/publico/<segredo>/<arquivo>` é a única do painel que não pede entrar.
7. **A escrita fica num módulo só** (`zervis/redes/instagram_publicar.py`): um contêiner por slide,
   o do carrossel com a legenda, a espera até ficar pronto e a publicação. `instagram.py` segue
   só leitura.

8. **Visual em cada slide (16/11/2026).** Só texto, o carrossel ficava sem imagem. O modelo
   escolhe, slide a slide, um visual que o Zé desenha com a paleta (`zervis/marketing_visual.py`):
   - um ícone da Lucide (63 ícones em `zervis/marca_icones.json`, ISC);
   - um fluxo de 2 a 4 passos;
   - um "antes e depois";
   - uma lista;
   - uma conversa de mensagens, sempre com o selo "Ilustração".
   
   Sem IA de imagem, sem banco de fotos e sem logo de terceiros.
9. **As fotos de quem usa** ficam em "Fotos da marca", em Marketing (`<dados>/marketing/fotos`,
   em JPEG até 1600 px). O nome do arquivo descreve a foto, e o modelo escolhe uma para a capa
   quando combina com o tema; a capa leva a foto embaixo, com um degradê na cor do fundo. As fotos
   ficam nesta máquina e só saem na publicação aprovada.

## Consequências

- Publicar exige o Instagram conectado com permissão de publicar e o acesso de qualquer lugar com
  endereço fixo; sem um deles, o painel diz qual falta.
- Reels e vídeo ficam para depois (precisam de geração de vídeo), assim como agendar posts.
