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
  baixado e conferido pelo Zé; as sessões de código alimentam e recebem a passagem dele.
- **Registros de funcionamento em SQLite** (`ze.db`): sessões, Foco, automações e tempos. O que o
  usuário edita (memória curta, skills no padrão `SKILL.md`) continua em arquivo.

## Próximos passos, em ordem

1. **Configuração da primeira vez no painel.** Feito: sem perfil, o painel abre nela (perfil com
   nome, sobre e fuso; acesso ao Claude por assinatura ou chave; chave do Deepgram). Falta:
   **"Ei Zé" genérico** que vem junto e funciona ao instalar, com "Personalizar a ativação" opcional
   (gravação de ~4 min com a voz de quem usa), proposto como passo da configuração inicial. O "Ei
   Zé" segue interrompendo a fala do Zé; a voz do Cadu entra no treino só como exemplo negativo. Depois:
   ai-memory e pasta dos projetos.
2. **Três camadas de modelos, sem o Orca (ADR 0015):** feito: a página Modelos com um cartão
   por camada (voz rápida, cérebro, sessões de código) e o modo manutenção sobre as sessões
   próprias, e o Orca fora do núcleo (o cérebro delega pelas ferramentas `sessao_*`). Feito também: contas por agente e o Codex nas sessões. Feito também: troca de conta ou de agente na mesma sessão. Falta: captura do Codex no
   ai-memory; a conversa continua na troca manual de cérebro, com o ai-memory comum aos dois.
   Feito: Codex na voz e no cérebro, com alternativas entre contas antes de texto ou ação (ADR 0020).
3. **Padrões que ainda supõem uma máquina:** microfone `omarchy_mic_fx` e o OmniRoute (baterias) como
   opcionais que se desligam sozinhos quando não
   existem; Omarchy detectado em vez de suposto. **Escuta sem depender de janela:** hoje o
   microfone só abre com a janela do painel (modo aplicativo) aberta, e a classe da janela é a
   mesma de qualquer Zé na máquina; vira um interruptor "Escuta" no painel e um atalho. O painel
   segue como página web, instalável como aplicativo (manifesto).
4. **Instalação de um comando** (Linux): o Zé e o painel como serviço do usuário (a voz já vem
   junto), o ai-memory e o imersivo; README de quem chega.
5. **SQLite** para os registros, com migração automática dos arquivos.
6. **Revisão final** antes do primeiro envio público (inclui os documentos antigos que ainda
   falam do Orca e do JARVIS: visão, conceitos, reaproveitamento, plano da oficina).
7. **VPS** sem tela e sem microfone; depois o celular.

## Em aberto

- Nome do pacote e das variáveis: o código ainda é o pacote `jarvis` e usa `JARVIS_*`; as pastas
  de dados e os serviços já se chamam `zervis`.

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
