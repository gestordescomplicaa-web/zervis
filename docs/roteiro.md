# Roteiro

O objetivo: o Zé completo no GitHub e fácil de instalar do zero, para qualquer pessoa. Ele espelha
o Hermes e o OpenClaw, só que mais enxuto, rápido e eficiente. Linux primeiro: Omarchy com o
controle completo da máquina, outro Linux (Ubuntu) com o controle reduzido e, depois, uma VPS sem
tela e sem microfone (painel, texto e, adiante, o celular). Windows fica fora por enquanto.

## Já decidido

- **Dados em três raízes XDG** (`jarvis/lugares.py`): `~/.config/zervis`, `~/.local/share/zervis`,
  `~/.local/state/zervis`.
- **"Quem sou eu"** em `<config>/perfil.json` (nome e sobre), lido por `jarvis/usuario.py`; a
  persona recebe isso no começo de cada conversa. Nenhum nome fixo no código.
- **Fuso** do sistema (`jarvis/fuso.py`), ou `JARVIS_FUSO`.
- **Voz só pelo Deepgram.** Sem a chave, o Zé não escuta (painel e teclado funcionam).
- **Acesso ao Claude** (`jarvis/cerebro/acesso.py`): token da assinatura (`claude setup-token`) ou
  chave de API colados no painel, senão o que a máquina já tem (variáveis ou login do Claude Code).
  Aplicado no ambiente do processo, vale para cérebro, via rápida, automações, sessões e revisão.
- **Licença AGPL-3** (ADR 0013).
- **Piper dentro do Zé** (dependência Python, GPL-3) e a voz Cadu (CC0) baixada e conferida na
  primeira subida: primeiro som em ~150 ms, sem serviço à parte.
- **Imersivo dentro do Zé** (ADR 0014): holograma, Núcleo e mãos em `jarvis/imersivo/`, subido
  pelo próprio Zé, com estado e manifesto nas pastas de dados.
- **Memória longa pelo ai-memory embutido** (MIT, ADR 0016): o da máquina, ou o binário oficial
  baixado e conferido pelo Zé; as sessões de código alimentam e consultam a memória comum.
  A passagem do trabalho atual é produzida pelo Zérvis a partir dos registros da sessão e Git.
- **Registros de funcionamento em SQLite** (`ze.db`): sessões, Foco, automações e tempos. O que o
  usuário edita (memória curta, skills no padrão `SKILL.md`) continua em arquivo.

## MVP: pronto para liberar (decidido em 15/10/2026)

O Zérvis ainda não está pronto. O caminho até a primeira versão pública é deixá-lo eficiente,
estável e instalável, e não somar funções. Função nova só entra se fechar uma lacuna do papel de
assistente de trabalho na [matriz comparativa](matriz-comparativa.md); o resto fica para depois
da liberação. Cada etapa tem um critério que se comprova, e só conta como feita com a prova.

| # | Etapa | Pronto quando | Estado |
|---|---|---|---|
| 1 | Filtro de qualidade | O painel abre num Chromium de verdade dentro do `make check` (todas as páginas, sem erro no console) e `make check-instalacao` passa numa pasta limpa | Feito em 15/10/2026 |
| 2 | Estabilidade | Painel sem quedas e terminal correto com duas telas abertas; tarefa retomada depois de reiniciar, sem repetir efeitos; automações validadas no uso; sem a camada de compatibilidade de `jarvis/nucleo/servicos/interface_*.py`; nenhum nome de pessoa no código ou nos dados gravados | ⬜ |
| 3 | Instalação de um comando | `install.sh` e o comando `zervis` (`setup`, `doctor`, `update`, `uninstall`, `status`) numa máquina Linux limpa e numa VPS sem áudio, sem Go nem Node instalados antes (o que precisa vem com o instalador); WaCalls por binário conferido por SHA-256. Plano, dificuldades de quem instala e o PC como estação de um Zé na VPS: [ADR 0034](adr/0034-central-estacoes-e-instalacao.md) | ⬜ |
| 4 | Eficiência medida | Latência da voz, memória, processos ociosos e tokens por tarefa medidos numa rotina repetível; README com números no lugar de "mais enxuto" | ⬜ |
| 5 | Liberação | Pacote `zervis` (com aliases para `jarvis` e `JARVIS_*`), documentos antigos revisados, README para quem chega, CI rodando `make check` e `make check-instalacao`, repositório público | ⬜ |

Depois da liberação: pacotes de extensão (ADR 0033, etapa E6), mais canais, isolamento em
contêiner e outras plataformas. A exceção a avaliar é conversar com o Zé pelo WhatsApp, que já
está pareado.

## Próximos passos, em ordem

**Antes dos próximos passos:** a reorganização do [ADR 0032](adr/0032-arquitetura-para-crescer.md)
(etapas E1 a E7: SQLite, núcleo dividido, painel tipado, pacotes e pronto para o público), uma
etapa por vez. Ela absorve os itens 5 (instalação), 6 (SQLite) e 8 (revisão final) abaixo.

1. **Configuração da primeira vez no painel.** Feito: sem perfil, o painel abre nela (perfil com
   nome, sobre e fuso; acesso ao Claude por assinatura ou chave; chave do Deepgram). Falta:
   **"Ei Zé" genérico** que vem junto e funciona ao instalar, com "Personalizar a ativação" opcional
   (gravação de ~4 min com a voz de quem usa), proposto como passo da configuração inicial. O "Ei
   Zé" segue interrompendo a fala do Zé; a voz do Cadu entra no treino só como exemplo negativo. Depois:
   ai-memory e pasta dos projetos.
2. **Três camadas de modelos, sem o Orca (ADR 0015):** feito: a página Modelos com um cartão
   por camada (voz rápida, cérebro, sessões de código) e o modo manutenção sobre as sessões
   próprias, e o Orca fora do núcleo (o cérebro delega pelas ferramentas `sessao_*`). Feito também: contas por agente e o Codex nas sessões. Feito também: troca de conta ou de agente na mesma sessão, captura dos turnos concluídos do Codex no
   ai-memory e orientação de busca na memória comum aos dois agentes.
   Feito: Codex na voz e no cérebro, com alternativas entre contas antes de texto ou ação (ADR 0020).
3. **Padrões que ainda supõem uma máquina:** microfone `omarchy_mic_fx` e o OmniRoute (baterias) como
   opcionais que se desligam sozinhos quando não
   existem; Omarchy detectado em vez de suposto. Feito: **escuta sem depender de janela**
   (ADR 0021): a escolha "Escuta" (Sempre ou Com a janela aberta), o Hyprland detectado e o
   microfone padrão do sistema quando o MIC FX não existe. Falta: o OmniRoute opcional e o painel
   instalável como aplicativo (manifesto), que também serve à voz remota.
4. **O Zé pelo celular e por outros aparelhos** (plano da voz remota; decisão de 12/10/2026). Dois
   públicos: quem desenvolve testando no próprio PC e quem instala do zero (Linux, PC ou VPS).
   Seguro por padrão: instalado, o Zé só responde no próprio PC; abrir para outros aparelhos é
   escolha explícita e sempre com senha. Em ordem:
   1. **Senha de acesso** para todo aparelho que não seja o próprio PC (uma vez por aparelho,
      "lembrar este aparelho"); senha mais código (TOTP) na internet aberta (VPS).
   2. **Áudio dentro do HTTPS** (WebSocket) como padrão do navegador, e a tela ligada durante o
      Ao vivo: se o painel abre, a voz funciona (Wi-Fi, 4G, Tailscale ou domínio), sem porta nem
      firewall. O LiveKit fica para o próprio PC e para telefone.
   3. **Assistente "Acesso pelo celular"** com dois modos: rede privada (Tailscale, já com as
      verificações de certificado e firewall) e domínio próprio (VPS, certificado automático).
   4. **Modelo de segurança dos canais** (ADR) antes de app ou ligação: nível de confiança por
      canal; nada destrutivo por telefone; o Zé liga para a pessoa, não o contrário.
5. **Instalação de um comando** (Linux): o Zé e o painel como serviço do usuário (a voz já vem
   junto), o ai-memory e o imersivo; README de quem chega; o modo servidor (VPS).
6. **SQLite** para os registros, com migração automática dos arquivos.
7. **Atendimento** ([plano](plano-atendente.md), ADR 0031): o Zé atende clientes no WhatsApp e
   no telefone, separado do Zé principal, com handoff para quem usa. Feito: o WhatsApp pareado
   pelo QR (WaCalls) e as mensagens como fonte dos avisos de lead quente. Falta: a recepcionista
   por ligação, o atendente no texto, montar o agente, assumir ao vivo e a telefonia SIP.
8. **Revisão final** antes do primeiro envio público (inclui os documentos antigos que ainda
   falam do Orca e do JARVIS: visão, conceitos, reaproveitamento, plano da oficina).

## Primeiro teste numa VPS real (16/10/2026)

O Zé foi instalado numa VPS (Ubuntu 24.04) pelo `docs/vps.md`: o instalador terminou, o painel
abriu pelo túnel SSH e o Zé continuou de pé depois de fechar o SSH (*linger*). O que apareceu,
na ordem em que resolver:

1. **Agentes na VPS** ([ADR 0035](adr/0035-agentes-prontos-na-instalacao.md)): Claude e Codex
   "Não instalado"; o Codex exigiu terminal; o cérebro não aceitava a chave da OpenAI. Feito: os
   dois vêm com o Zé, e o Codex aceita a chave da OpenAI pelo painel. Falta: o login da conta do
   ChatGPT pelo painel (hoje, `codex login --device-auth` no terminal).
   Testado na VPS em 16/10/2026: a voz pelo navegador (Ao vivo) e pelo celular funcionou, com a
   chave da OpenAI nas Respostas rápidas. O cérebro ficou sem acesso: a lista dele mostra só
   Claude, Codex e OmniRoute, e quem procura "OpenAI pela chave" não acha. O login das contas (Claude e Codex) pelo painel não funcionou: no
   servidor, "Entrar" tentava abrir um terminal que não existe. Feito em seguida: o login pelo
   painel, com o link e o campo do código, para os dois.
   Testado na VPS em seguida: a conta do Codex entrou pelo painel e o cérebro Codex respondeu (com
   o gpt-6-luna; o modelo padrão deu "acesso inválido" na conta). Mas o cérebro não usava nenhuma
   ferramenta do Zé (sessões, lembretes): os modelos novos do Codex chamam as ferramentas por um
   auxiliar, `codex-code-mode-host`, que vem num pacote à parte e o Zé não baixava. Feito: o Zé
   baixa e confere o auxiliar junto com o Codex, inclusive numa instalação anterior. Faltam:
   - a revisão da conversa usa sempre o Claude; com só o Codex conectado, ela falha no registro.
     Deve usar o cérebro em uso;
   - o modelo padrão do Codex que a conta não aceita: o Zé deveria escolher um que ela aceite.
   - um Codex instalado à mão sem o auxiliar (o caso da VPS: só o binário em `~/.local/bin`) tem a
     vez e deixa o cérebro sem ferramentas; o Zé deve usar o dele nesse caso.
   Testado na VPS depois do auxiliar: o cérebro Codex viu a sessão e mandou mensagem a ela. Criar
   uma sessão nova travou: a ferramenta exigia o caminho da pasta. Feito: cada sessão nova ganha a
   própria pasta em `~/projetos` (o nome da sessão), o nome de um projeto existente vale como
   pasta, o agente padrão é o que tem conta conectada e o primeiro commit sai mesmo sem nome no git.
2. **Entregar o código numa VPS:** com o repositório privado, o `git clone` pede usuário e token do
   GitHub (contornado com `git archive` e `scp`). Resolve com o repositório público e o instalador de
   um comando (ADR 0034, etapa I3).
3. **Túnel e porta:** o painel só aceita a mesma porta dos dois lados, e o PC de quem desenvolve já
   usa a 8795; foi preciso parar o Zé do PC durante o teste.
   Latência do painel (medida em 16/10/2026): o Zé responde cada leitura em menos de 15 ms e a VPS
   está folgada; a lentidão da troca de aba é a distância até a VPS (uma ida e volta por aba).
   Feito: a aba aparece na hora com o desenho anterior e se atualiza depois. Uma VPS no Brasil
   também ajudaria a voz.
   Autodesenvolvimento na VPS: "não foi possível unificar pelo Git" vinha de o pacote enviado por
   `git archive` não ter o `.git`. Feito: o instalador cria o histórico local e o erro diz o que
   fazer.
4. **Aba Imersão no servidor:** aparece vazia pelo túnel (busca a porta 8794); esconder quando o Zé
   está num servidor.
5. **Modelos de voz faltando:** o painel não mostra; só o registro.
   **Escuta que falha às vezes (VPS, 16/10/2026):** o Deepgram recusou a conexão quatro vezes
   seguidas e voltou sozinho; o registro dizia só "InvalidStatus". Feito: o registro diz o motivo
   (chave, crédito, limite) e uma recusa passageira tenta de novo uma vez. Próximo: **Opus na voz
   do navegador.** Hoje o microfone vai em PCM de 16 kHz (256 kbit/s) e a voz do Zé volta em PCM,
   pelo WebSocket do painel; no 4G e pelo túnel, isso pesa e a conexão cai (código 1006). Com Opus
   (WebCodecs no navegador, libopus no Zé), cerca de 24 kbit/s em cada sentido. O Zé decodifica
   antes do "Ei Zé" e do Deepgram, que seguem com PCM.
6. **Chaves digitadas no comando:** uma chave colada direto num comando fica no histórico do shell;
   com o item 1, chave só pelo painel.
7. **Contribuições e atualizações:** como a comunidade propõe melhorias (PR, CI, aprovação de quem
   mantém) e como quem personaliza pelo autodesenvolvimento atualiza para uma versão nova sem perder o
   que é seu. Vira um ADR antes da liberação.

## Em aberto

- Nome do pacote e das variáveis: o código ainda é o pacote `jarvis` e usa `JARVIS_*`; as pastas
  de dados e os serviços já se chamam `zervis`.

## Andamento da atualização (15/10/2026)

### Correção do alerta e do reenvio ao trocar conta (16/10/2026)

O texto do terminal só solicita conferência: não marca limite, não muda estado e não anuncia
créditos esgotados. A transcrição precisa confirmar o bloqueio após a abertura do processo atual.
Uma atualização de saldo não torna recente um erro antigo. O limite fica vinculado à conta;
marcas legadas sem essa identificação deixam de alimentar o alerta e a retomada automática.

Escolher uma conta apenas altera a conta. Reenviar o pedido exige o botão explícito Continuar
ou o fallback após prova recente. A API recusa continuar por um aviso que já não vale, e a
troca com envio é serializada para impedir dois reenvios por cliques concorrentes. Se a
manutenção foi desligada, um comando enfileirado não é encaminhado à central. O seletor e a
faixa acompanham a conta atual; respostas atrasadas de outra sessão são ignoradas.

Regressões com transcrição antiga redesenhada, conta com saldo, timestamp de saldo após erro
antigo, marca herdada de outra conta e registro legado; Chromium escolhe uma conta com alerta
ativo sem reenviar e acompanha a mudança de conta no backend. Testes de comando enfileirado e
API impedem o encaminhamento indevido. Os dados de uso e os saldos reais não foram alterados.
Validação: `make check` aprovado com 991 testes, formatação, lint, tipos Python e JavaScript,
`go vet` e testes Go. A correção entra em uso após aprovar e aplicar pelo painel.

### Fallback automático de contas

Sessões comuns e autodesenvolvimento tentam outra conta cadastrada do mesmo agente após limite
confirmado, na ordem Pro, Plus e Gratuita, preservando modelo e esforço. Contas de plano
desconhecido vêm depois. O catálogo local determina compatibilidade, sem presumir saldo.
Sem evidência do pedido/configuração atual ou sem conta compatível, avisa e aguarda escolha.
O trabalho continua na mesma pasta e conversa, com instrução de conferir ações já concluídas.

Contas esgotadas e tentativas ficam em SQLite, impedindo ciclos. Atualizar, interromper ou agir
manualmente impede a retomada pendente. O terminal acompanha a troca sem recarregar a página;
o aviso de troca não é anunciado como conclusão. Ver ADR 0016.

Provas: cadeia com contas sintéticas nas sessões comuns e na central; PTY real encerrado antes
da nova conta, transcrição atual substituindo cópia antiga, modelo/esforço do turno preservados,
texto sem erro estruturado recusado, reserva e cancelamento. Chromium confere a continuidade
da leitura após trocar de processo. Nenhum crédito real foi consumido; aplicar e observar um
limite real depende da atualização aprovada no painel.

### Continuidade e espaço do terminal

A passagem entre agentes usa o último pedido e sua resposta literal, conserva ressalvas finais
e distingue o relato do agente do estado registrado. O delta continua limitado; cortes são
indicados e o histórico registrado da sessão fica disponível num arquivo privado para consulta.
O prompt de passagem é retirado antes de guardar o pedido e oferecer retomada, inclusive no
Claude. Históricos importados não substituem o pedido da central. Ver ADR 0016.

Captura dos turnos concluídos do Codex pelo ai-memory, respeitando sua política e sanitização;
fila limitada fora do laço das sessões, sem impedir trabalho quando a memória falha. Ambas as
ferramentas recebem, nas novas conversas e passagens, orientação de busca na mesma memória e
no projeto original. A troca automática foi acrescentada na etapa descrita acima. Não há
migração de memórias antigas nem alteração de configurações globais.

O cartão Sessão central só aparece quando há unificação a fazer, em andamento ou pendente.
Concluir mostra um aviso temporário e libera o espaço do terminal, inclusive ao reabrir a página.
O Codex abre com `--no-alt-screen`, preservando a saída na rolagem. O painel oculta a barra
nativa vazia da viewport antiga do xterm 6 e mantém a barra da biblioteca, com contraste no tema.
Provas com dados sintéticos: roda do mouse e clique na barra no Chromium, leitura de histórico
sem saltar para a saída nova, confirmação da unificação e reabertura da central; regressões de
pedido recente, ressalvas, importações, privacidade e falha da memória. Aplicação em uso depende
da aprovação no painel; agentes já abertos precisam reabrir para receber os novos argumentos.

Validação: `make check` aprovado com 973 testes, estilo, tipos Python e JavaScript, `go vet`
e testes do Go. Prévia conferida no Chromium com dados sintéticos. Prova adicional com o
ai-memory real em uma raiz temporária: duas cópias, um projeto e uma conversa nativa, com
pedidos, respostas permitidas pela configuração de captura e encerramento registrados.
Nenhuma conta ou configuração do Zérvis em uso foi alterada.

### Sessão central de autodesenvolvimento

#### Resolução de cópias antigas

Na consolidação, uma cópia antiga trazia a implementação de pacotes de extensão, adiada pelo
roteiro mais recente, e um rascunho que renomeava a pasta Python sem ajustar os imports.
A resolução preserva a estrutura e as decisões da central. Os commits e o rascunho completos
ficam alcançáveis pelo histórico Git da central, para retomada posterior, sem reativar trabalho
adiado nem substituir correções recentes.

Corrigida a repetição do conflito após a resolução manual: um rascunho com a mesma árvore e
mesmo commit de origem reutiliza sua fotografia Git. Se já há uma fotografia reconciliada no
histórico da central, ela tem preferência. Alterações novas de conteúdo ou de base continuam
sujeitas à conferência. Regressões com datas diferentes, fotografias irmãs, renomeação resolvida
na central, importação do histórico e preservação das origens. Aplicar a correção antes de
repetir Unificar sessões permite concluir a importação dos históricos.
Validação: `make check` aprovado com 962 testes, tipos, estilo e Go. A regressão da
renomeação falhou com o código anterior e passou com a correção. O histórico real da cópia
antiga foi reconciliado na branch central; a importação dos registros aguarda aplicar e
repetir Unificar sessões no painel.

#### Funcionamento

Uma sessão por projeto e perfil, com a mesma cópia e branch em Claude, Codex, contas e modelos.
O vínculo no SQLite sobrevive à perda do estado JSON. Recuperação não filtra pelo agente;
referência ausente com várias candidatas exige escolha, e pasta ou registro perdidos não
autorizam criar outra cópia. As aberturas concorrentes compartilham a mesma central.

No próprio PC, Unificar sessões reúne as cópias legadas na atual, com confirmação e sem trabalho
em andamento. A central precisa estar sem alterações locais; rascunhos das outras cópias são
preservados em fotografias Git e integrados quando não há conflito. O banco recebe backup
privado; conversas e pendências entram com a origem identificada. Pastas, arquivos ignorados,
branches e conversas nativas antigas continuam preservados. As sessões substituídas recusam
novos comandos. Atualizar, descartar e reiniciar aguardam a migração. Ver ADR 0026.

Provas sintéticas: três cópias com commits e rascunhos, índice original preservado, conflitos,
colisão com ignorados, interrupção após Git e retomada sem duplicar mensagens, recuperação do
vínculo e aberturas simultâneas, Claude e duas contas Codex com passagem ainda pendente.
Chromium confere a escolha da central, confirmação persistente entre consultas, reserva do
terminal, reabertura após concluir e altura da tela. A migração dos dados reais é acionada no
painel depois de aplicar esta versão; os dados pessoais não foram migrados durante os testes.
Fallback de contas foi acrescentado na etapa acima. Troca automática de modelo continua fora
do escopo, conforme a preferência explícita de quem usa.
Validação local: `make check` aprovado com 960 testes, formatação, lint, tipos Python e
JavaScript, `go vet` e testes do Go. Os testes usam contas e dados temporários.

### Delegação por voz e resultados de sessões

O envio mantém a especificação completa na ferramenta, mas a confirmação falada usa apenas
"Estou enviando sua solicitação à sessão X, confirma?". O nome vem da sessão resolvida e seu
identificador fica fixado antes de perguntar, inclusive quando o pedido usou a sessão em foco.
Um aviso de outro projeto durante a confirmação não redireciona a solicitação. Negar continua
impedindo o envio. A criação de sessão com tarefa também usa a confirmação curta.

Cada resultado é anunciado pelo nome em Normal e Mãos livres, inclusive com a sessão aberta;
Silencioso continua só na tela. O resumo compara o pedido com a resposta e preserva pendências
e impedimentos. Se o modelo falhar, há uma citação curta da resposta. Três sessões concluídas
geram três falas sequenciais, sem pedir "próximo", sem sobrepor falas e esperando a pessoa
terminar de falar. A fila preserva os avisos concorrentes e grava com permissão privada.

Provas com dados sintéticos: aprovação e negativa em Claude e Codex, chamada MCP real, prompt
completo preservado e mudança de foco durante a confirmação; três resultados guardados e
anunciados separadamente; pessoa falando, Silencioso, gravações simultâneas e falha do resumo.
A escuta na máquina em uso depende de aplicar a versão pelo painel e conferir um pedido real.

### Aviso antes do reinício

O aviso passa a ser "Atualização aprovada, reiniciando automaticamente.", a pedido de quem usa,
para reduzir a fala que estava sendo cortada pelo reinício. O teste existente confere a frase
exata; a confirmação audível depende de aplicar esta versão pelo painel e acompanhar o próximo
reinício.
Validação local: `make check` aprovado com 922 testes, estilo, tipos e Go.

### Reserva das sessões durante a aplicação

Do clique em Aplicar até o resultado da atualização, novos pedidos, teclas do terminal e a
abertura de novos agentes ficam bloqueados, inclusive no autodesenvolvimento. Trabalhos que já
estavam em curso podem terminar; a leitura de saídas e conversas continua disponível. O painel
mostra a reserva junto ao terminal. Falha ou cancelamento da espera liberam o envio, preservando
o pedido interrompido e descartando teclas recusadas. A conferência das sessões e a reserva
compartilham a trava do envio para não admitir um pedido durante essa transição (ADR 0028).

Provas: pedido concorrente com Aplicar; espera sem bloquear o laço da voz; terminal real via
HTTP recusando teclas, novos agentes e retomadas, com leitura preservada em todas as etapas;
Chromium mostrando a reserva e descartando teclas em fila, inclusive após cancelar a espera.
Sucesso, falha e volta liberam o envio. `make check` aprovado com 922 testes, além de estilo,
tipos e Go. A aplicação no Zérvis em uso permanece sujeita à aprovação pelo painel.

### Recuperação da sessão de autodesenvolvimento

Corrigido o caso do Claude parado no limite semanal enquanto a sessão permanecia trabalhando:
o aviso passa a reconhecer limites semanal, diário e de sessão, inclusive com ANSI ou dividido
entre quadros. A troca de agente ou conta usa a mesma sessão e cópia; o estado da manutenção
acompanha a escolha e não abre outra cópia ao voltar à página. O painel oferece Interromper com
confirmação para encerrar o agente, preservando arquivos e conversa, e explica quando é preciso
entrar em manutenção para aplicar. A troca e a interrupção ficam bloqueadas durante a atualização.

Provas: limite em vários quadros; troca com Git real mantendo commits, rascunho e pedidos;
terminal real encerrado antes de liberar a troca; Chromium interrompendo com confirmação,
escolhendo Codex, reabrindo a página e marcando a revisão antes de aplicar. Testes sem agentes
ou contas reais. A passagem entre agentes é limitada, como nas sessões comuns (ADR 0016).
`make check` aprovado: 912 testes, além das verificações de estilo, tipos e Go.

### Etapas visíveis

A aplicação de melhorias informa as etapas reais pelo painel: verificar a cópia, juntar,
verificar a atualização e reiniciar. O cartão permanece ao navegar, mostra tempo decorrido e
uma estimativa baseada nas durações anteriores. O percentual fica abaixo de cem até o script
confirmar que o processo novo iniciou. Falha e retorno à versão anterior têm resultado próprio.

O andamento é publicado atomicamente em `manutencao/progresso.json` (0600), na raiz de estado,
e sobrevive à troca de processo. O resultado permanece por dez minutos, ou até ser fechado na
aba. A gravação desse indicador nunca impede a atualização; uma falha de disco aparece no log.
Reinício sem confirmação expira; uma interrupção nos testes não vira sucesso. O serviço impede
duas aplicações simultâneas, inclusive com dois painéis. Sair da manutenção cancela a espera.

Provas: regressões de recuperação, falha, expiração, gravação privada e pedidos simultâneos;
Git real em projeto temporário com as etapas da manutenção; Chromium com API HTTP e o módulo
real de progresso, navegando durante a atualização, recarregando após a troca de processo,
mostrando sucesso, falha e volta. A desconexão é esperada somente na etapa de reinício e por
tempo limitado. A instalação em uso continua passando pela revisão e aplicação no painel.

Validação local: `make check` com **905 testes** aprovados, incluindo os três cenários de
andamento no Chromium; formatação, lint, mypy, TypeScript e testes do Go aprovados. Prévia
conferida visualmente em uma instância com dados sintéticos.

Na primeira instalação deste recurso, a versão anterior só exibe o aviso de atualização que já
possuía. O acompanhamento das etapas começa nas aplicações seguintes, com a versão nova no ar.

### Atualização pequena para conferir o andamento

A descrição de Autodesenvolvimento passa a ser "Revise e aplique melhorias. Acompanhe a
atualização até o reinício." É uma mudança de texto para exercitar a aplicação pelo painel e
conferir a versão nova depois do reinício. Não exige teste dedicado de lógica; a abertura da
página e o fluxo de progresso já são cobertos pelos testes de navegador do `make check`.
Validação local: `make check` aprovado, com 912 testes, verificações de estilo e tipos e Go.
O acompanhamento da aplicação real depende de aprovar esta atualização no painel.

## Confiabilidade antes da distribuição (12/10/2026)

Correções da avaliação de maturidade:

- **Sessões:** a exclusão bloqueia cópias com alterações, arquivos novos ou ignorados. A remoção
  usa a proteção do Git, sem `--force`; falha na verificação ou remoção preserva a sessão.
- **Imersivo:** Host e Origin locais; token por instância nos pedidos e nas leituras de estado.
  A página, os cards do núcleo e os comandos `board.sh`/`board-state.sh` enviam a autorização.
  O token de terminal fica na pasta de estado com permissão 0600 (ADR 0019).
- **Distribuição:** personas em `jarvis/persona/`, incluídas no wheel. Conferido construindo o
  pacote, extraindo fora do repositório e importando as personas e o ponto de entrada. Os caminhos
  anteriores em `persona/` são links para os mesmos arquivos, para processos já em execução
  continuarem lendo a persona até o próximo reinício.
- **Memória longa:** consulta e publicação usam o mesmo resolvedor de binário e `--data-dir`;
  conversas e notas podem usar o ai-memory embutido mesmo fora do PATH.
- **Calibração:** a etapa de resultado espera a gravação terminar. Durante a gravação, mantém
  os gestos suspensos e informa que está salvando; teste com gravação bloqueada deliberadamente.

Provas locais: regressões com Git, HTTP e scripts reais em pastas temporárias; Chromium sem tela
com a autorização real, verificando pedidos locais e ausência de token em outro servidor; suíte
do imersivo com mãos simuladas. Nenhuma chave, perfil ou dado de uso foi alterado.

Resultado em 12/10/2026: `make check` aprovado (formatação, lint, tipos e **611 testes**);
`make check-imersivo` aprovado (**12 testes**, 102,21 s). O wheel foi
construído com `uv build --wheel`, extraído em uma pasta temporária e importado a partir dela:
as duas personas foram lidas pelo núcleo e `main(["--version"])` respondeu. Os testes de
regressão novos falhavam antes das correções. As alterações locais anteriores foram preservadas.

Próximas etapas: isolamento equivalente entre agentes, serialização dos registros e migração para
SQLite, critérios verificáveis de entrega e avaliação de pedidos reais. A instalação completa em
outra distribuição e o desempenho de voz com hardware continuam pendentes.

### Exclusão de sessões em execução (12/10/2026)

Feito: a exclusão encerra o agente e espera seus callbacks ou a limpeza da tarefa assíncrona.
O terminal encerra seu grupo de processos e o comando em primeiro plano, com escalada para
SIGKILL e confirmação do fim. Abrir, enviar, ler eventos e excluir não disputam o ciclo de vida
da sessão. A pasta original e alterações em cópias isoladas continuam protegidas (ADR 0017).

O isolamento completo continua pendente: conversas são separadas, mas a cópia dos arquivos é
opcional; contas, instruções globais e memória podem ser compartilhadas. A sandbox dos motores
ainda não é equivalente. O contador de consumo cobre respostas do cérebro, revisão e automações;
não cobre os terminais das sessões, e os motores HTTP da via rápida ainda não capturam `usage`.

Validação: `make check` aprovado com **618 testes**. Regressões com terminal real e HTTP local
confirmam exclusão durante execução, espera pelos callbacks e cancelamento assíncrono, preservação
do projeto e encerramento de subprocessos que ignoram sinais, com ou sem saída ligada ao terminal.
O serviço foi reiniciado na máquina; painel e imersivo responderam HTTP 200, a API de sessões
continuou acessível e o status confirmou um processo novo, batimento recente e nenhum erro.

### Voz com contas de agentes — verificação em 12/10/2026

- `make check`: 628 testes passaram, formatação, lint e tipos sem erros.
- Codex respondeu pela conta alternativa; ferramenta MCP sintética executada uma vez, com
  resultado confirmado. Automático passou pela conta indisponível sem intervenção.
- Serviço reiniciado; voz rápida configurada em Automático. Teste pela API do painel: resposta
  em 3,44 s, primeiro texto em 3,30 s. Chromium confirmou Automático selecionado e Codex habilitado.
- Pedido pelo teclado do imersivo foi recusado pelo estado Inativo. A reprodução de voz e o
  microfone continuam pendentes de uma prova com a sessão ativa; não se contornou essa proteção.

### Correções prioritárias da auditoria de maturidade

- A autorização de ferramentas do Codex agora faz parte da zona protegida do autodesenvolvimento.
- Agendamentos serializam a leitura, alteração e publicação, inclusive entre instâncias do mesmo
  arquivo no processo. Cada escrita usa um temporário exclusivo, que já nasce com permissão 0600.
- Sessões comuns com cópia isolada têm prévia, Aplicar e Descartar no painel, com confirmação.
  Erro de consulta ou comando Git interrompe a operação; o descarte preserva arquivos ignorados
  e recusa colisões com a versão do projeto. O terminal ocioso fecha antes de alterar a cópia.
- Sessão trabalhando, operação Git em andamento e alterações locais no projeto impedem aplicar.
  Cópias do autodesenvolvimento continuam passando pelo fluxo próprio de revisão.

Provas: regressões com agendamentos simultâneos; Git real em projetos temporários, com conflitos,
ponteiro inválido, falha no reset e na limpeza, colisões de arquivos ignorados e terminal real.
No Chromium, os botões só alteraram os arquivos depois da confirmação; aplicar mudou o projeto,
mas descartar mudou somente a cópia. Instalação e dados pessoais preservados.

Verificação final: `make check` aprovado com **781 testes**; teste da interface de cópias no
Chromium aprovado. Serviço reiniciado com duas sessões paradas; painel e imersivo HTTP 200,
sessões preservadas e endpoints novos recusando operações sem confirmação (HTTP 400).
