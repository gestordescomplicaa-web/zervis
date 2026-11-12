# 0083 — Fatiar e imprimir pela rede local, com o sim de quem usa

- Data: 12/11/2026
- Status: **Aceita** (`tests/test_impressao3d.py`; com a impressora real, só leitura: achar na
  rede, o status, o cartão e o fatiamento com o filamento dela. A primeira impressão de verdade
  fica com quem usa, por perto.)

## Contexto

Os Projetos 3D (ADR 0082) entregam o STL e a prévia; faltava imprimir. A impressora de quem usa é
uma Bambu Lab A1. Ela não tem API oficial aberta: no modo só LAN com o modo desenvolvedor ligado,
ela aceita o MQTT dela (status e comandos) e o FTPS do cartão, na rede local, com o código de
acesso. O Bambu Studio da máquina fatia por linha de comando.

## Decisão

1. **A conexão é de quem usa** (`<config>/impressora3d.json`, permissão só do dono): IP, número de
   série e código de acesso. A tela nunca recebe o código de volta. "Procurar na rede" acha a
   impressora sozinha: quem tem a porta 8883 aberta na mesma rede /24 e um certificado da Bambu,
   cujo nome é o número de série (e o começo dele diz o modelo).
2. **O status pelo MQTT** (`pushall`), em português: parada, imprimindo (com a porcentagem e o
   tempo que falta), pausada, concluída ou com falha; as temperaturas e o filamento de cada
   bandeja do AMS.
3. **Fatiar é do Zé, com o Bambu Studio da máquina** (o pacote ou o Flatpak), numa pasta de
   trabalho do projeto (`.ze/impressao/`), que é também a pasta corrente (ele grava um
   `result.json` onde estiver). O perfil da máquina vem do modelo; o de filamento, da bandeja que
   vai ser usada (a marca, senão o genérico do tipo). A linha de comando não aceita perfil que
   herda: o Zé junta a cadeia. Sai o tempo, os gramas e a frase: "Leva 41 min e 25 g de PLA Lite
   da bandeja 2."
4. **Imprimir pede o sim:** pela voz, `projeto3d_imprimir` passa pela aprovação falada, e o
   cérebro diz antes o tempo e o filamento (`projeto3d_fatiar`); no painel, uma confirmação que
   lembra de deixar a mesa livre. A impressora só recebe trabalho parada. O 3MF sobe para o cartão
   (FTPS implícito, com a sessão TLS reaproveitada no canal de dados) e o `project_file` começa,
   com o nivelamento da mesa e a bandeja escolhida. Pausar, retomar e parar também pedem o sim.
5. **O fim vira aviso:** depois de mandar, o Zé olha a impressora a cada minuto e avisa quando a
   impressão termina ou para antes do fim.

6. **O envio não espera o fechamento do TLS** (12/11/2026, na primeira impressão de verdade). A
   Bambu não responde ao fechamento do TLS no canal de dados, e o `storbinary` do `ftplib` ficava
   esperando até o prazo (30 s) com o arquivo já inteiro no cartão; o Zé desistia e nunca mandava
   começar. Agora o canal só fecha, e a confirmação vem na hora (10 s para 400 KB, com a A1). Se
   mesmo assim ela não vier, vale o arquivo no cartão com o tamanho certo.

## Consequências

- No modo desenvolvedor, a impressora sai da nuvem da Bambu: o app Bambu Handy e o acesso de fora
  deixam de funcionar. Quem usa escolheu isso.
- O formato do `project_file` segue o que as bibliotecas da comunidade usam com a A1; a primeira
  impressão confirma. A câmera (porta 6000) ainda não é usada: conferir a mesa antes de imprimir
  é a próxima melhoria.
- Uma dependência nova, `paho-mqtt` (EPL-2.0 ou EDL-1.0).
