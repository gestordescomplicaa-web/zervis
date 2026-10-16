# Instalar no PC Linux

Use o terminal da sessão gráfica de um usuário comum, com systemd do usuário ativo. No Ubuntu
24.04 com desktop, instale os pré-requisitos:

```sh
sudo apt install git make curl xdg-utils pulseaudio-utils
git clone https://github.com/gestordescomplicaa-web/zervis.git
cd zervis
deploy/instalar-pc.sh
```

O instalador reaproveita a preparação do servidor: uv fixado, `uv sync --frozen`, modelos de
voz conferidos e agentes de código. Instala o serviço `zervis` do usuário, habilita o início
automático e abre `http://127.0.0.1:8795/`. Configure perfil, conta Claude ou Codex e Deepgram no
painel. Sem Deepgram, a conversa por texto funciona. A instalação não configura acesso externo.

O atalho Zérvis fica no menu de aplicativos. Ele usa Chromium ou Chrome, inclusive os nomes
`chromium-browser` e `google-chrome-stable`; sem eles, abre o navegador padrão por `xdg-open`.
As pastas XDG são respeitadas, inclusive quando seus caminhos têm espaços.

```sh
systemctl --user status zervis
journalctl --user -u zervis -f
```

Se a porta 8795 já estiver ocupada, encerre a outra instância antes de instalar. A escolha
automática de porta e o comando `zervis doctor` continuam previstos no ADR 0034.

## Verificação

Os testes de `tests/test_instalador_pc.py` executam os scripts reais e o `make instalar` em
pastas temporárias com espaços. Rede, agentes e systemd são substituídos por comandos falsos:
conferem serviço, atalho, abertura local, recusa de root e de sessão sem tela, e preservação
do modo servidor. O navegador padrão e os nomes diferentes do Chromium têm testes próprios.

A CI acrescenta a prova em Ubuntu 24.04 com tela virtual (Xvfb), systemd do usuário real e
Chromium com sandbox: executa o instalador, confere o serviço ativo e habilitado, o atalho
instalado e a aba aberta no endereço local. Não usa contas pessoais nem simula audição.

`make check-instalacao` prepara também os modelos de som no ambiente vazio, antes dos testes;
assim `ZE_SEM_PULOS=1 make check-instalacao` não perde a prova das features ONNX por falta deles.

Microfone, saída de som e controle do desktop precisam da prova num PC físico antes de declarar
o item 1 de “Onde estamos” concluído. Na sessão gráfica de um Ubuntu 24.04 limpo:

1. Execute os comandos de instalação acima; o painel deve abrir na configuração inicial.
2. Configure as contas pelo painel, envie uma mensagem e confira a resposta.
3. Configure Deepgram, teste o microfone e confira uma resposta falada.
4. Feche a janela e abra Zérvis pelo menu; reinicie a sessão e confira o serviço e o atalho.
5. Registre aqui o resultado e a versão testada, sem chaves ou dados pessoais.

Essa prova física permanece pendente. A CI com tela virtual não comprova os dispositivos de áudio.
