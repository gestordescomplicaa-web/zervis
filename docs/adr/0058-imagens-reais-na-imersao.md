# 0058 — Imagens e vídeos reais na Imersão: a foto de quem é, ao lado dos hologramas

- Data: 03/11/2026
- Status: **Em validação** (testado contra a Wikimedia de verdade e no Chromium; falta a pessoa
  aprovar o visual numa cena pedida por voz).

## Contexto

As cenas (ADR 0047) mostram gráficos, hologramas, modelos 3D e mapas, mas nada de verdade: "quem
é fulano e o que ele faz na política?" pedia a foto da pessoa, não um desenho. Pedido de
03/11/2026: imagens reais e animações, buscadas na internet, como mais uma habilidade nativa do
Zé, só com o que é gratuito.

## Decisão

1. **Fontes gratuitas e com licença em cada arquivo, sem chave** (`zervis/imersivo/imagens.py`):
   a Wikipédia (pt, depois en), cuja foto principal da página é a melhor para pessoas públicas,
   lugares e empresas; e o Wikimedia Commons, para fotos e vídeos de qualquer assunto (o vídeo na
   versão leve, 480p em webm). Google e Bing Imagens ficam de fora: API paga, bloqueio de robô e
   nenhuma licença por imagem. O Openverse fica para depois (sem chave, 5 buscas por hora).
2. **As travas dos modelos 3D** (ADR 0049): só HTTPS e só os domínios da Wikimedia, também nos
   redirecionamentos; teto de tamanho; o conteúdo conferido pelos bytes (JPEG, PNG, WebP, GIF,
   WebM); imagem marcada como não livre (uso justo) recusada. Vai para o Acervo
   (`imagens/web/`, `videos/web/`) com um `.json` da fonte, licença e autor; o que já foi
   baixado é reusado sem ir à rede.
3. **O print de uma página** (`zervis/imersivo/capturas.py`): o Chromium da máquina, sem tela e
   com perfil descartável. Todo o tráfego dele passa por uma trava local, que só aceita CONNECT
   para endereço público na porta 443, resolvendo o nome uma vez só. O painel do Zé, a rede de
   casa, o Tailscale e qualquer serviço da máquina ficam de fora. QUIC desligado e WebRTC sem UDP
   fora da trava.
4. **Blocos foto e video nas cenas**: um quadro realista (sem o tom, as linhas e a varredura do
   holograma), a foto nítida com um leve zoom lento, a legenda sobre ela e o crédito no rodapé do
   painel ("FOTO: AUTOR · LICENÇA · FONTE"). Nunca ESQUEMA nem ILUSTRATIVO. A página só aceita
   arquivo de `imagens/` (foto) ou `videos/` (webm) do Acervo, pelo corredor `/media/`.
5. **Ferramentas, livres** (só leem a Wikimedia ou a página pedida e só gravam no Acervo):
   `imagem_buscar` (com as prévias, para o Zé escolher olhando), `imagem_baixar` e
   `pagina_capturar`. "Quem é/quem foi" com a janela aberta vai ao cérebro completo, como
   "explica".
6. **Cuidado com pessoas**: foto de pessoa só de figura pública (com página na Wikipédia); nunca
   ilustração ou holograma no lugar da foto de alguém. Sem foto livre, o Zé diz e segue sem ela.
