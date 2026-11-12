# 0078 — A abertura: música e o resumo do dia ao abrir o Zérvis

- Data: 11/11/2026
- Status: **Aceita** (os testes do panorama e das rotas no `make check`; a abertura inteira num
  Chromium de verdade em `tests/imersivo/test_abertura.py`).

## Contexto

Abrir o Zérvis caía no Início do painel, sem nada do dia: nem a saudação certa para a hora, nem a
agenda, nem as sessões que ficaram no meio, nem o clima ou as notícias. Assistentes no estilo do
Jarvis abrem com uma música e um panorama do dia, e isso é o que quem usa vê primeiro.

A Imersão já tinha quase tudo: os painéis holográficos da apresentação (ADR 0045), ligados ao Zé
por feixes e que as mãos pegam, e a voz do Zé para avisos. É a primeira função nova da Imersão
depois do congelamento do ADR 0071, que valia até a 0.5.0; a revisão geral do foco fica para um
ADR próprio.

## Decisão

1. **Abrir o programa é a abertura.** O atalho (`deploy/abrir-painel.sh`) abre o painel com
   `?abertura=1`. O painel vai para a Imersão e passa o pedido a ela uma vez só: o endereço
   esquece o pedido, e recarregar (uma atualização, por exemplo) não repete. No celular, e com a
   configuração inicial por fazer, não há abertura. A janela do atalho toca som sem um clique antes
   (`--autoplay-policy=no-user-gesture-required`), só nela.
2. **O roteiro:** a música de quem usa toca e o nome acende; o Zé vai para o canto e cada bloco do
   dia vira um painel, falado com a voz dele: a saudação pela hora com a data, o clima, a agenda e
   as automações de hoje, as sessões de código que pedem continuidade (interrompidas, no limite da
   conta, com erro ou trabalhando), as conversas do WhatsApp sem resposta nas últimas 24 horas (sem
   as silenciadas) e as manchetes do Brasil. Bloco vazio não entra. A música abaixa enquanto o Zé
   fala. Os painéis ficam no quadro no fim; Esc pula a abertura. "Apresenta o meu dia" refaz o
   roteiro sem a música (a ação `apresentar` com `dia`).
3. **O Zé monta o dia; a página só desenha.** O Zé grava o panorama em `abertura.json` uma vez por
   minuto (e na hora em que chega clima ou notícia nova), pelo mesmo contrato de arquivos do
   autoconhecimento. Para falar, a página manda só o número do passo e o panorama
   (`POST /abertura/falar`); o texto falado é sempre o que o Zé montou. A fala entra como um aviso
   pedido: com o Zé livre, fala na hora; numa conversa ou ligação, espera a vez. Sem a voz, a
   página segue pelo tempo da legenda.
   Um assunto por vez: a página pede a fala primeiro, e o painel e a legenda chegam com a voz (ou
   depois de 2,5 s, se ela demorar); o próximo espera o Zé terminar.
   Visto no primeiro uso (11/11/2026): no Silencioso a voz ficava muda, e a abertura corria sem
   falar. Um aviso pedido (a abertura, o "Ouvir" do celular) agora sai mesmo no Silencioso: foi a
   pessoa que pediu. E a música tocava num elemento de áudio, que o Zé pausa como qualquer player
   enquanto fala ("pausar mídia"): ela agora toca pela Web Audio, que não é um player.
4. **As fontes de fora não gastam tokens nem pedem chave:** o clima pelo Open-Meteo (dados sob
   CC BY 4.0, com o crédito no painel) e as manchetes pelo RSS do Google Notícias Brasil, com a
   Agência Brasil de reserva. Ficam em cache por 20 minutos, buscadas fora do laço do Zé; uma
   falha só tira o bloco.
5. **Os ajustes são de quem usa** (cartão Abertura, na página Perfil): ligar ou desligar, a cidade
   do clima (vazia, a do fuso: `America/Fortaleza` vira Fortaleza) e a música, guardada em
   `<dados>/abertura/` e conferida pelo começo do arquivo (MP3, OGG, WAV ou M4A, até 20 MB). Sem
   música, a página sintetiza uns poucos tons. Nada disso vai para o repositório.

6. **Foco, Instagram e gráficos pequenos** (11/11/2026, segunda versão). Entram o card do Foco
   (a frente atual, o próximo passo e as frentes por estado, em barras) e o do Instagram, só com
   a conta conectada (seguidores, publicações da semana e as visualizações das seis mais novas,
   em colunas). O clima ganha a curva da temperatura do dia, hora a hora (o mesmo pedido ao
   Open-Meteo), e a agenda, a linha do dia com cada compromisso. Com mais de seis cards, eles se
   arrumam em quatro colunas. O Instagram lê só as publicações mais novas
   (`Instagram.recentes`), aproveitando o cache, para não gastar o limite da Meta.
7. **Os avisos não atropelam a entrada.** A página avisa o Zé quando a abertura começa e quando é
   pulada (passos -1 e -2 do mesmo `POST /abertura/falar`). Enquanto ela roda, e nos primeiros
   segundos depois de o Zé subir, quando ela está ligada, todo aviso vai para a fila e nada é
   oferecido; a oferta vem depois do fechamento. O "bom dia" separado não repete o dia. Avisos sem
   manchete viram uma conta só ("Três novidades esperando"), nunca "um aviso, um aviso e um aviso"
   (visto em 11/11/2026).
8. **A abertura não vira aviso nem conversa** (11/11/2026, à noite). Os "avisos sem manchete" eram
   as próprias falas da abertura: uma que chegava com o Zé ocupado ia para a fila durável e voltava
   depois, fora de hora ("Boa tarde, Gabriel" à noite). E a música, no microfone, soava como o
   "Ei Zé": ele abria uma conversa no meio da entrada e passava a ouvir depois de cada fala. Agora,
   durante a abertura, o chamado por voz não vale (o botão vale, e o Esc a pula); uma fala dela
   que não couber na hora é descartada; e as que já estavam na fila saem dela antes de qualquer
   oferta (reconhecidas pelo jeito: `panorama.JEITO_DE_FALA`).
9. **A abertura espera o dia completo** (11/11/2026, à noite). Abrir o programa sobe o Zé, e o
   primeiro panorama sai antes de terminar a primeira busca de fora: a página lia esse e abria só
   com a hora, o Foco e o WhatsApp. O panorama agora diz se está `completo` (a primeira busca do
   clima, das manchetes e do Instagram terminou); a página mantém o nome na tela, com a música,
   até ele chegar, por até 12 segundos (sem rede, abre sem esses blocos).
10. **As cenas pelo menu do Zé** (11/11/2026, terceira versão). Oito cards iguais numa grade
    liam como um painel de controle. A abertura passa a ter cinco cenas, agrupadas como o menu:
    **Agora** (a hora com os segundos, a saudação e o clima, com a curva da temperatura e a chance
    de chuva hora a hora), **Hoje** (a agenda e as automações num mostrador de 24 horas, o próximo
    compromisso e o Foco), **Redes sociais** (o WhatsApp sem resposta e o Instagram, num painel
    só), **Atividade** (os pedidos, as ações e as falhas de sete dias, as automações que rodaram
    hoje e as sessões trabalhando) e **Pendências** (o que espera quem usa, cada item com a seção
    do menu onde se resolve: sessões paradas, automações que falharam, melhorias prontas do
    autodesenvolvimento, sugestões de memória e atualização disponível). As manchetes passam numa
    faixa sob o mosaico. Cada cena entra grande, no centro, enquanto o Zé fala dela, e depois
    encaixa no lugar dela; no fim fica o mosaico inteiro. Os painéis são desenhados para uma tela
    de 1600 por 900 e escalados inteiros, para ficarem iguais em qualquer tela. Sob o nome, na
    entrada, as cenas do dia acendem quando o Zé tem o dia completo.
    O clima cruza com a agenda sem gastar tokens: o Zé diz a partir de que hora chove e avisa do
    compromisso que cai numa hora de chuva. No WhatsApp ele fala nomes, nunca números de telefone
    (lia dígito por dígito), e o resto vira "e mais duas". As melhorias prontas são contadas pelo
    git fora do laço, junto com as outras fontes de 20 minutos.

## Consequências

- Abrir o programa leva uns 40 a 60 segundos de apresentação; quem não quiser desliga no Perfil
  ou aperta Esc.
- O nome dos contatos do WhatsApp e os títulos da agenda são falados em voz alta ao abrir.
- O Zé consulta o Open-Meteo e o Google Notícias a cada 20 minutos enquanto roda, com a cidade
  configurada. Nenhum outro dado sai da máquina.
- A abertura lê a Atividade do Zé uma vez por minuto, como o autoconhecimento já fazia.
- Com o Instagram conectado, o Zé lê o perfil e as publicações mais novas a cada 20 minutos (uns
  dez pedidos por hora à Meta, só leitura).
