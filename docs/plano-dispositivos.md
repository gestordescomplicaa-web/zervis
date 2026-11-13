# Plano: Dispositivos, a casa conectada (13/11/2026)

O pedido do usuário: a impressora 3D, a TV e a câmera viraram abas e código específicos dentro
do Zé. Para quem baixa, isso é pessoal e confunde. Em vez de uma aba por aparelho, ele quer um
"Integrar dispositivos": o Zé lê o que existe na rede local, pergunta o que a pessoa quer de cada
aparelho e abre uma sessão de código para fazer a integração. É IoT (casa conectada), feito do
jeito do Zé: pela voz, com as contas de quem usa e com sessões de código de verdade.

Decisão de arquitetura: [ADR 0089](adr/0089-dispositivos-locais.md).

## O que já existe (e o que é genérico)

| Peça | Onde | Específico do aparelho | Genérico (fica no núcleo) |
|---|---|---|---|
| Impressora Bambu (ADR 0083, 0085) | `impressora3d.py`, `impressora_vigia.py` | MQTT/FTPS da Bambu, câmera da porta 6000 | aviso com foto ao celular, vigia que reconecta |
| Modo TV (ADR 0084) | `tv/` | a página no navegador da TV | mostrar algo numa tela da casa |
| Câmera iCSee (ADR 0087, 0088) | `camera.py`, `camera_vigia.py`, `atendimento/camera_fala.py` | DVRIP/Sofia, `MsgtoNetEnable`, a ordem `Claim` → `Start` | foto por evento, galeria, **aparelho como canal de voz**, agente isolado para quem não é você, ponte com o celular |
| Imagem no celular (ADR 0086) | `transporte/navegador.py` | — | tudo |

O que mais vale nesses PRs é a coluna da direita. Ela serve para qualquer aparelho.

## Princípios

1. **De quem usa** (essência 3): a varredura é só na rede local e só quando a pessoa pede. Os
   aparelhos, as credenciais e as integrações geradas ficam nas pastas dela, nunca no
   repositório.
2. **Segurança acima da conveniência** (essência 5):
   - o Zé nunca adivinha nem força senha: pede à pessoa;
   - ação com efeito físico (imprimir, falar na rua, abrir, ligar) começa pedindo confirmação;
   - quem não é você (a rua, um cliente) fala com um agente isolado, sem ferramentas.
3. **Nada de aparelho no núcleo.** O núcleo sabe *trabalhar com aparelhos*; o protocolo de cada
   um mora numa integração.
4. **Integração não roda dentro do Zé** (ADR 0033): ela roda em processo próprio e conversa com
   o Zé por uma API local.
5. **Tudo registrado** na Atividade (essência 6), inclusive a varredura e o que foi negado.
6. **Linguagem de produto:** a seção se chama **Dispositivos**. "IoT" fica na documentação.

## Como fica

### Para quem usa

- **Painel → Dispositivos.** Sem nenhum aparelho, a seção mostra só "Procurar dispositivos". Nada
  de câmera, impressora ou TV para quem não tem.
- **"Procurar dispositivos"** explica antes o que vai fazer: ler a rede local e as portas
  conhecidas. Ao fim, lista o que achou, cada aparelho com o endereço e uma etiqueta:
  - **Reconhecido:** há integração pronta, como "Câmera Xiongmai/iCSee" ou "Impressora Bambu
    Lab".
  - **Desconhecido:** o fabricante pelo endereço da placa e as portas abertas.
- **Para cada aparelho, "O que você quer dele?"**, por texto ou voz: "foto quando passar
  alguém", "conversar pela câmera", "avisar quando a impressão acabar".
  - **Com integração pronta:** o Zé pede as credenciais, testa ("Conectada") e liga o que foi
    pedido.
  - **Sem integração:** "Criar integração" abre uma **sessão de código** com o briefing pronto
    (endereço, portas, assinatura, fabricante e o pedido). A sessão descobre o protocolo e
    testa no aparelho com a pessoa junto ("passe na frente da câmera agora"). Ela entrega uma
    integração no formato de pacote, que só entra com a aprovação na tela (ADR 0033).
- **Cada aparelho integrado** tem um cartão com o estado (Conectado, Sem conexão), os ajustes e
  o que a integração oferece: galeria, conversas, impressão, botões.

### Por dentro

- **Registro de dispositivos** (SQLite, ADR 0032): id, nome dado pela pessoa, endereço, tipo,
  integração, estado e permissões. As credenciais vão para o cofre.
- **Descoberta:**
  - varredura TCP da /24 privada da máquina, nas portas do catálogo;
  - mDNS e SSDP;
  - fabricante pelo OUI do endereço físico;
  - assinatura de cada integração conhecida. Exemplos: Xiongmai abre 34567 e mostra "Web
    Viewer"; Bambu abre 8883, 990 e 6000 e tem certificado com o número de série; TVs aparecem
    em DIAL/SSDP; Home Assistant abre 8123.
- **Integração = pacote** (formato da ADR 0033), em `DADOS/dispositivos/<id>/`. Ela traz:
  - o manifesto: aparelho, assinatura, o que oferece, os campos do cadastro e as permissões
    sugeridas;
  - um **conector** (MCP, stdio) com as ferramentas, como `camera_foto` ou `impressora_status`;
  - uma skill que diz como usá-lo.
- **Barramento local** (API com token, como a da Central): é por onde uma integração usa o
  núcleo, que ela não acessa direto. Ela pode:
  - **avisar** um evento, com foto ou não;
  - **mostrar** uma imagem no celular ou no painel;
  - **abrir um canal de voz** (o aparelho fala e ouve), com o agente isolado da Central;
  - **guardar** arquivos na pasta dela.

  O núcleo decide o que vira aviso, fala ou foto no celular, segundo os ajustes de quem usa.
- **Interface declarada, não HTML de pacote:** o manifesto descreve cartões, campos, botões e
  galerias, e o painel desenha com os componentes dele. Um pacote não injeta código no painel.
- **Integrações oficiais** (`integracoes/` no repositório): a Bambu, a iCSee/Xiongmai e a TV
  passam a ser as três primeiras, no formato de pacote. Elas são catálogo: só se instalam quando
  o aparelho é achado e a pessoa escolhe.
- **Home Assistant** é uma integração como as outras: pelo conector MCP dele, entram de uma vez
  os aparelhos que ele já controla. O diferencial do Zé é a sessão que integra o que ninguém
  suporta, e a voz por cima de tudo.

## A versão pública e a estável

O que vale hoje (13/11/2026):

- O repositório é **público**: o que entra na `master` qualquer um vê.
- **Quem atualiza** (`zervis atualizar`, ou "Atualizar" no painel) vai para a última **versão
  publicada** (hoje a `v0.4.0`). Só o modo de desenvolvimento segue a `master`.
- **Quem instala do zero** segue o README (`git clone`) e recebe a **`master`**, não a versão
  publicada. É isso que faz o que acabou de ser mesclado chegar a quem baixa.

Decisão: a `master` é desenvolvimento; quem baixa recebe a versão publicada.

## Fases

As Fases A e B do [plano de maturidade](plano-maturidade.md) congelam funções novas. As fases 0
e 1 daqui são correção e reorganização, e cabem nelas. Da 2 em diante, só depois da 0.5.0, junto
com a Frente 4 (alcance).

### Fase 0: proteger quem baixa (antes da próxima versão)

- [x] O instalador (`deploy/instalar-pc.sh`, `deploy/instalar-servidor.sh`) faz checkout da
      última versão publicada logo depois do `git clone` (PR #181). O README diz isso, e o modo de
      desenvolvimento continua existindo para quem quer a `master`.
- [x] As seções de aparelho só aparecem com o aparelho cadastrado. Isso foi feito junto com a
      Fase 1: o menu tem só "Dispositivos", que lista o que está cadastrado e oferece "Adicionar
      dispositivo". Sem esse "Adicionar", esconder as abas tiraria o único lugar de cadastrar.

### Fase 1: a seção Dispositivos, sem mudar comportamento

- [x] A seção **Dispositivos** junta a câmera (que sai da aba própria), a impressora (o cadastro
      e o estado saem de Projetos 3D, que continua sendo a criação dos modelos) e o Modo TV (que
      sai de Perfil). Cada aparelho tem a sua página (`#camera`, `#impressora`, `#tv`), com o
      menu marcando Dispositivos.
- [x] A lista única de dispositivos (`zervis/dispositivos.py`) é lida dos cadastros atuais
      (`camera.json`, `impressora3d.json`, `tv.json`), sem mover nem migrar nada. No PC de quem
      já usa, nada muda de lugar. O registro em SQLite vem com as integrações (fase 3), que é
      quando os cadastros mudam de formato.
- [x] A voz lista os aparelhos e o estado deles (`dispositivos_listar`). Para agir, continuam as
      ferramentas de cada um.

### Fase 2: procurar dispositivos

- [ ] "Procurar dispositivos" com o catálogo de assinaturas, mDNS, SSDP e OUI, mostrando o
      reconhecido e o desconhecido.
- [ ] "O que você quer dele?" guardado no registro, para a integração e para a sessão.

### Fase 3: integrações como pacotes

- [ ] O barramento local: avisar, mostrar, canal de voz e guardar, com token e registro na
      Atividade.
- [ ] A interface declarada no manifesto.
- [ ] As três integrações oficiais migram para pacote, em processo próprio. O núcleo perde
      `impressora3d.py`, `camera.py` e companhia, e os testes acompanham a mudança.
- [ ] A permissão por ferramenta de cada aparelho (livre, com confirmação, proibida), no cartão
      dele.

### Fase 4: criar integração

- [ ] "Criar integração" abre uma sessão de código (ADR 0015) numa pasta isolada, com o briefing
      do aparelho e regras fixas:
  - nunca tentar senha;
  - pedir à pessoa o que faltar;
  - testar no aparelho de verdade;
  - entregar no formato de pacote;
  - não sair da pasta.
- [ ] O fim da sessão é a tela de aprovação da ADR 0033 (o que o pacote instala e as
      permissões) e o "Testar" no cartão.

### Fase 5: Home Assistant

- [ ] A integração pelo MCP do Home Assistant: os aparelhos dele entram no registro, com as
      mesmas permissões e a mesma voz.

## Riscos

- **Varredura é sensível:** sempre a pedido, só na rede privada da máquina, nunca fora dela,
  e registrada.
- **Integração gerada é código de terceiro:**
  - roda em processo próprio, sem acesso ao resto;
  - entra no sandbox quando a Frente 2 entregar o bubblewrap;
  - começa com tudo pedindo confirmação.
- **Aparelho real é imprevisível:** a câmera precisou de quatro descobertas que só apareceram
  testando (a senha do aparelho, o alarme desligado de fábrica, a ordem `Claim` → `Start`, as
  lentes invertidas). A sessão precisa da pessoa e do aparelho por perto, e o plano não promete
  integração automática sem isso.
- **Escopo:** isto não substitui o Home Assistant. O Zé conversa com ele.

## Pronto quando

- Quem instala do zero recebe a versão publicada e não vê nenhuma aba de aparelho que não tem.
- No PC do usuário, Dispositivos mostra a câmera, a impressora e a TV funcionando como hoje.
- Um aparelho desconhecido sai de "Procurar dispositivos" para "Criar integração" e chega a um
  cartão funcionando, com a pessoa aprovando o pacote, sem nenhuma linha no núcleo do Zé.
