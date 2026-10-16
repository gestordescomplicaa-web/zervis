# 0034 — Central e estações, e a instalação de um comando

- Data: 16/10/2026
- Status: **Proposta** (pedido da pessoa em 16/10/2026: o Zé completo numa VPS, com as mesmas
  funções do PC, e instalação fácil para terceiros, com o mínimo de etapas). Os pontos 6 e 7
  mexem na essência (item 5) e só valem depois da revisão da pessoa no próprio computador.
- Detalha as etapas 3 e 5 do MVP no [roteiro](../roteiro.md) e a E7 do
  [ADR 0032](0032-arquitetura-para-crescer.md). Traz para antes a etapa 6 ("Estações") do
  [plano da voz remota](../plano-voz-remota.md). Usa a voz pelo HTTPS do
  [ADR 0024](0024-voz-pelo-https.md).

## Contexto

Na máquina de quem desenvolve, o Zé funciona bem. Numa VPS, não: ele supõe que microfone,
alto-falante, janela, projetos e logins estão no mesmo computador. E instalar ainda é `git clone`,
`uv sync` e `make instalar`, com Go para o WhatsApp e downloads que podem falhar na primeira
subida.

As referências resolveram isso de dois jeitos:

- **OpenClaw** separa o cérebro das mãos. O *Gateway* roda no servidor; cada aparelho (Mac,
  celular, Linux sem tela) roda um *node* que **liga para o Gateway** pelo WebSocket, é pareado
  por QR ou código com aprovação e oferece os próprios comandos (câmera, tela, notificações,
  sistema).
- **Hermes** entrega tudo num comando: o `install.sh` traz uv, Python e as dependências, sem
  sudo, cria o comando `hermes` e oferece `hermes doctor`. Onde ele pensa e onde ele executa são
  coisas separadas (terminal local, Docker, SSH ou Modal).

O Zé já tem as peças para os dois: a entrada de áudio remota (`jarvis/transporte/entrada.py`), a
voz pelo HTTPS do painel, o túnel num serviço próprio, senha com código do autenticador, binários
de terceiros conferidos por SHA-256 (ai-memory, cloudflared, livekit-server), o Claude Code
embutido no `claude-agent-sdk` e o `make check-instalacao`.

## Decisão

### Central e estações

1. **Um pacote, dois papéis.**
   - **Central** (VPS ou PC): cérebro, contas, memória, skills, Foco, sessões de código,
     automações, avisos, painel, atendimento no WhatsApp, Deepgram e Piper.
   - **Estação** (o PC de quem usa): o mesmo pacote rodando `zervis estacao`. Oferece o que só
     existe naquela máquina.
   - Com o Zé só no PC, Central e estação são o mesmo processo, sem rede entre elas. Nada muda
     para quem usa hoje.
2. **A estação liga para a Central**, pelo WebSocket do próprio painel (HTTPS, a mesma porta).
   Ninguém abre porta, firewall ou roteador. Funciona por qualquer caminho que o painel alcança:
   túnel, domínio, Tailscale ou rede local.
3. **Pareamento por código de uso único**, gerado no painel da Central (página Estações) e
   digitado em `zervis estacao parear`. Cada estação recebe um token próprio, guardado em arquivo
   0600 nos dois lados e revogável na página. Estação sem token não conecta.
4. **Catálogo fechado de capacidades**, declaradas pela estação ao conectar e aprovadas uma a uma
   no pareamento:
   - **Áudio:** microfone e alto-falante do PC, no mesmo protocolo da voz do navegador
     (ADR 0024). O "Ei Zé" é detectado **na estação**, e o áudio só vai para a Central depois do
     chamado ou com o Ao vivo ligado: menos tráfego e a mesma privacidade de hoje.
   - **Sistema:** as ações do catálogo do Omarchy (`jarvis/sistema/`), com a política de risco.
   - **Mídia:** pausar e retomar o que toca enquanto o Zé fala.
   - **Sessões:** sessões de código nos projetos da estação, com o terminal transmitido ao
     painel da Central.
   - **Imersivo:** câmera e holograma na tela da estação.

   Não existe comando livre: a estação executa só o que está no catálogo. Uma ação nova entra
   no catálogo por código revisado, nunca por mensagem da Central.
5. **A política vale nos dois lados.** A Central pede; a estação confere de novo pela própria
   política, recusa o que não reconhece e registra na Atividade da Central, inclusive o que
   negou. Ação perigosa pede confirmação na estação (falada ou na tela dela).
6. **"O próprio computador" na VPS** (essência, item 5). Hoje, aplicar, reiniciar, mudar ajustes
   de acesso e a zona protegida só valem no próprio PC. Na VPS não há tela local. Proposta: valem
   o terminal da VPS (o comando `zervis`, por SSH) e a estação marcada como **principal** no
   pareamento. O celular e o painel aberto de fora continuam sem esse poder.
7. **Estação desconectada:** as funções dela aparecem como "Indisponível" e o motivo
   ("Estação desconectada"); avisos e conversa continuam pelo navegador e pelo celular. Um pedido
   que precisa da estação fica no Foco até ela voltar, sem repetir efeitos.
8. **Voz na VPS:** o navegador (celular ou PC) é o microfone, como já é (ADR 0024); a estação é
   a outra entrada. O LiveKit fica para telefone e SIP: na VPS ele exige portas UDP abertas e
   TURN, passos que quem instala não deveria fazer. Comprimir o áudio do WebSocket (Opus) fica
   para depois, com medição.

### Instalação de um comando

9. **Um comando, sem sudo, como usuário comum:**

   ```sh
   curl -fsSL https://<endereço do projeto>/install.sh | sh
   ```

   O instalador:
   - confere Linux, glibc 2.28 ou mais nova, x86-64 ou arm64, systemd, espaço em disco e `make`,
     e recusa root (orienta criar um usuário);
   - instala o uv, se faltar, e o Python fixado pelo uv;
   - clona o repositório num lugar gerenciado (`~/.local/share/zervis/app`, na tag da versão).
     É um clone Git porque o autodesenvolvimento trabalha sobre ele;
   - roda `uv sync --frozen`;
   - baixa e confere por SHA-256 tudo o que vai junto (ponto 11);
   - instala o serviço do usuário e liga `loginctl enable-linger`, para o Zé continuar de pé
     depois de sair do SSH;
   - escolhe uma porta livre, se a 8795 estiver ocupada;
   - no PC, abre o painel na configuração inicial; na VPS, mostra o endereço e um código de
     configuração de uso único.
10. **O comando `zervis`:** `setup`, `doctor`, `status`, `update`, `uninstall` e `estacao`.
    O `doctor` mostra, por função, "Disponível" ou "Indisponível" e o motivo, com o passo exato
    para resolver (inclusive o pacote certo da distribuição).
11. **O Zé vai completo.** O instalador traz tudo o que não depende da máquina:

    | Camada | O que tem | Como chega |
    |---|---|---|
    | Vai junto | Python e dependências; Claude Code (embutido no `claude-agent-sdk`); Piper e a voz Cadu; modelos de ativação, de voz e de fim de turno; ai-memory; cloudflared; WaCalls **já compilado**; Codex CLI; Node fixado (navegador do Zé e `tsc`); Chromium sem tela (navegador do Zé e testes do painel); three.js e MediaPipe do imersivo | Baixado pelo instalador, conferido por SHA-256, sem sudo, sem Go |
    | Vem da máquina | PipeWire ou PulseAudio (`parec`, `paplay`, `pactl`), Hyprland ou Omarchy, câmera | Detectado, não instalado: é o próprio computador. Só faz sentido na estação |
    | Contas | Deepgram, Claude ou Codex, QR do WhatsApp | Configuradas na tela, como hoje |
    | Sob demanda | Go (só para o autodesenvolvimento mexer no WaCalls); livekit-server (só com telefone) | Baixado e conferido quando a função é ligada |

12. **Falha por função, não o Zé inteiro.** Se um download falhar, o painel e a conversa por texto
    sobem mesmo assim; a função afetada aparece como "Indisponível" e o `doctor` tenta de novo.
13. **Espelho próprio.** Os arquivos de terceiros que a licença permite redistribuir (CC0,
    Apache-2.0, MIT, BSD) ficam também nas releases do projeto, com os mesmos SHA-256 num
    manifesto (`deploy/arquivos.toml`). A origem oficial vira a alternativa.
14. **Atualizar sem perder as melhorias locais.** O que o autodesenvolvimento aplica fica numa
    branch local. `zervis update` busca a tag nova, reaplica a branch local sobre ela numa cópia
    isolada, roda o `make check` e só troca a versão em uso se tudo passar. Conflito ou falha:
    fica a versão atual, e o painel oferece uma sessão de autodesenvolvimento para resolver.
    A volta automática (ADR 0028) continua valendo.
15. **Docker é opcional**, não o caminho principal: uma imagem para quem prefere, construída
    pelo mesmo instalador, em base glibc (Debian), com `--init`, as três raízes XDG em volumes e
    só o papel de Central.
16. **A CI prova cada versão:** `make check` com Chromium e Go; `make check-instalacao` em
    Ubuntu 24.04, Debian 12 e Fedora (x86-64) e Ubuntu (arm64); os binários do WaCalls e o
    manifesto de SHA-256 publicados na release.

## Dificuldades para quem instala (levantamento de 16/10/2026)

Feito sobre o commit `bb3b168`: leitura do código, `make check`, `make check-instalacao` numa
pasta limpa e o Zé subindo numa máquina sem áudio e sem tela, com o HuggingFace bloqueado. A D24
apareceu depois, na CI da etapa I1.

**Impedem a instalação ou o uso na VPS**

| # | Dificuldade | Evidência | Resolve |
|---|---|---|---|
| D1 | Instalação manual: clone, uv, `make instalar` | README; matriz comparativa, seção 2 | Pontos 9 e 10 |
| D2 | A primeira subida depende do HuggingFace e do GitHub; se um download falha, o Zé não sobe | Teste de 16/10: "não consegui baixar pt_BR-cadu-medium.onnx" e o processo parou | Pontos 12 e 13 |
| D3 | Na VPS, o serviço do usuário para ao sair do SSH | Nenhum `enable-linger` no repositório; `systemd/zervis.service` é serviço de usuário | Ponto 9 |
| D4 | O WhatsApp exige Go e compila na primeira conexão (~1 min, baixa módulos) | ADR 0031, item 2 | Pontos 11 e 16 |
| D5 | Funções da VPS dependem do PC: microfone, tela, mídia, projetos | `jarvis/transporte/local.py` usa `parec` e o socket do PulseAudio do usuário | Pontos 1 a 8 |
| D6 | Imagens mínimas de VPS não têm `make`, e o autodesenvolvimento chama `/usr/bin/make -s check` | `jarvis/oficina/manutencao.py:106` e `:488` | Ponto 9 (confere) e 11 |

**Atrapalham ou deixam funções pela metade**

| # | Dificuldade | Evidência | Resolve |
|---|---|---|---|
| D7 | O Codex CLI não vem junto (o Claude Code vem, dentro do `claude-agent-sdk`) | `jarvis/cerebro/catalogo.py:121` e `jarvis/cerebro/rapido.py:632` procuram o `codex` no PATH | Ponto 11 |
| D8 | O navegador do Zé (Playwright MCP) é instalado à mão; nenhum código o instala | Só citado em `THIRD_PARTY.md` | Ponto 11 (Node e Chromium) |
| D9 | O imersivo carrega three.js e MediaPipe de CDNs a cada abertura: sem internet não abre, e cada abertura é um pedido a terceiros | `jarvis/imersivo/web/stage.html:286`, `:333` e `:2477` | Ponto 11 (vai junto, conferido) |
| D10 | O atalho do painel chama `chromium`, que tem outro nome no Ubuntu (snap), no Fedora e no Chrome | `deploy/abrir-painel.sh` | Detectar o navegador ou abrir o padrão; painel instalável (PWA) |
| D11 | O áudio local supõe `parec`, `paplay` e `/usr/bin/pactl`; algumas distribuições não trazem `pulseaudio-utils` | `jarvis/transporte/local.py` | Ponto 10 (`doctor` com o pacote certo) |
| D12 | O autodesenvolvimento passa pelo `make check`, que precisa de Node (`tsc`) e de Chromium (testes do painel) na máquina de quem usa | `Makefile`, alvo `tipos` | Ponto 11 |
| D13 | Sem Chromium, os testes do painel são pulados e o `make check` passa assim mesmo: a prova some sem aviso, inclusive no `check-instalacao` | `tests/test_painel_no_navegador.py:31` | Na CI e no autodesenvolvimento, falta de Chromium é falha, não pulo |
| D14 | Não há caminho de atualização a partir de uma versão publicada; melhorias locais e versões novas vão divergir | `jarvis/oficina/manutencao.py` trabalha só sobre o clone local | Ponto 14 |
| D15 | Porta fixa 8795 por padrão | `jarvis/portal/servidor.py:32` | Ponto 9 |
| D16 | O endereço do túnel rápido muda quando o computador reinicia; na VPS, o celular pareado perde o endereço | `CHANGELOG.md` (túnel num serviço próprio) | Domínio próprio no assistente "Acesso pelo celular" |

**Riscos para quem instala**

| # | Risco | Evidência | Resolve |
|---|---|---|---|
| D17 | Rodar como root, padrão de muitas VPS: os agentes de código ganham acesso total, e o Chromium exige `--no-sandbox` | Teste de 16/10 num contêiner root | Ponto 9 (recusa root) |
| D18 | Em contêiner sem init, processo zumbi conta como vivo e a exclusão de sessão falha | `jarvis/oficina/terminal.py:175`; 2 testes de `tests/test_terminal.py` falham nesse ambiente | Corrigir o `encerrar`; `--init` na imagem (ponto 15) |
| D19 | Contas obrigatórias fora do Zé: Deepgram (cadastro e uso pago) para ouvir; Claude ou Codex para pensar | Configuração inicial | Links diretos e "Testar" na configuração inicial; texto funciona sem Deepgram. Conferir os termos de uso de cada provedor antes da liberação |
| D20 | WhatsApp por protocolo não oficial: o número pode ser restringido pela Meta | ADR 0031, consequências | Aviso na página e número dedicado (já previsto) |
| D21 | Só glibc 2.28 ou mais nova: Alpine (musl) e distribuições antigas não instalam (onnxruntime, livekit e piper-tts só têm rodas `manylinux_2_28`) | `uv.lock` | Ponto 9 (confere e explica) |
| D22 | Nome misto: pacote `jarvis`, variáveis `JARVIS_*`, comando `zervis` | Roteiro, "Em aberto" | MVP, etapa 5 |
| D23 | `livekit` e `segno` sem versão exata, contra a regra de qualidade | `pyproject.toml` | Fixar num commit próprio |
| D24 | No Ubuntu 24.04, um Chromium baixado (sem perfil do AppArmor) aborta ao abrir o sandbox: vale para o Chromium que o instalador trouxer | CI de 16/10/2026: os 12 testes do painel abortavam até liberar `kernel.apparmor_restrict_unprivileged_userns` | Instalar o perfil do AppArmor do Chromium trazido (como o Chrome oficial faz) ou usar o do sistema; nunca tirar o sandbox |

## Ordem de execução

Uma etapa por vez, cada uma com prova, como no ADR 0032.

| Etapa | O que entra | Pronto quando |
|---|---|---|
| I1. Base | D13, D18, D23; CI com `make check` completo | A CI roda `make check` com Chromium e Go em cada envio, sem testes pulados |
| I2. Release | WaCalls compilado (x86-64 e arm64); espelho e manifesto de SHA-256; Codex, Node, Chromium e imersivo no manifesto | Uma máquina sem Go conecta o WhatsApp; o imersivo abre sem internet |
| I3. Instalador | `install.sh` e o comando `zervis` (pontos 9, 10 e 14); falha por função nos downloads (ponto 12), junto com o modo sem áudio da VPS | `check-instalacao` na CI nas quatro distribuições; numa VPS real sem áudio: painel, voz pelo celular e uma sessão de código terminando com aviso falado |
| I4. Estação | Pareamento, áudio, sistema e mídia; depois sessões nos projetos da estação | Zé na VPS e o PC como estação: "Ei Zé" no PC, uma ação do Omarchy e a música pausando enquanto ele fala |
| I5. Docker | Imagem opcional a partir do instalador (ponto 15) | A imagem sobe com volumes vazios e passa no `doctor` |

## Consequências

- O protocolo da estação é superfície de ataque nova: token por estação, revogação, catálogo
  fechado e política nos dois lados são obrigatórios desde a primeira versão.
- O instalador vira peça crítica: cada versão só sai com o `check-instalacao` aprovado na CI.
- Ir completo pesa algumas centenas de MB a mais (Node, Chromium sem tela, modelos), em troca de
  nenhum passo manual e do autodesenvolvimento funcionando na máquina de quem instala.
- Na VPS, as funções do PC dependem da estação estar ligada. Sem ela, o Zé continua útil pelo
  navegador e pelo celular: conversa, voz, sessões dos projetos da VPS, automações e atendimento.

## Andamento

| Etapa | Estado | Resultado |
|---|---|---|
| I1 | Concluído em 16/10/2026 | D18: o terminal não conta zumbi como processo vivo (teste novo cria o zumbi de propósito). D13: com `ZE_SEM_PULOS=1`, teste pulado e Go ausente são falha. D23: `livekit` e `segno` fixados, com teste que vigia a regra. CI no GitHub (`.github/workflows/check.yml`, Ubuntu 24.04): `make check` completo com Chromium, modelos de som, Node e Go, aprovado em 4 min 52 s, sem teste pulado. Na CI apareceu mais uma dificuldade: no Ubuntu 24.04, o AppArmor aborta o sandbox do Chromium, e a CI libera a restrição só na máquina dela. O ponto 12 passou para a I3: o núcleo carrega os modelos de voz ao subir (`jarvis/nucleo/laco.py:211-226`), e subir sem eles é o mesmo modo sem microfone da VPS. |
| I2 a I5 | ⬜ | |
