# 0074 — Sessões protegidas: o agente só enxerga a pasta do projeto

- Data: 09/11/2026
- Status: **Aceita** (testado no `make check`, com o `claude` e o `codex` desta máquina dentro do
  isolamento, e na primeira sessão protegida de verdade, criada pelo painel em 10/11/2026).

## Contexto

As sessões rodam o Claude e o Codex como o próprio usuário, com permissão de editar sem
perguntar. Um agente enganado por um arquivo do projeto, uma página ou um conector consegue ler
o `~/.ssh`, as chaves do `~/.config` e os dados do Zé. É o primeiro item da Frente 2 do
[plano de maturidade](../plano-maturidade.md): "uma sessão não lê `~/.ssh/id_*` nem os dados do
Zé".

## Decisão

1. **Uma sessão pode ser protegida** (painel → Nova sessão → "Protegida"). O agente dela roda no
   bubblewrap (`zervis/oficina/isolamento.py`): o sistema só para leitura e a pasta pessoal
   trocada por uma vazia.
2. **Dentro, só o necessário:**
   - com escrita: a pasta do projeto (ou a cópia isolada, com o `.git` de verdade dela), a pasta
     da sessão no Zé, onde o agente conta o que faz, e a pasta de login da conta do agente;
   - só leitura: o que faz os programas rodarem (`mise` e as instalações dele, o Claude Code, o
     `~/.local/bin`, o `~/.gitconfig`), o Python do Zé (um gancho usa) e o `ai-memory`.
   Fora ficam o `~/.ssh`, o resto do `~/.config`, os dados do Zé e das outras sessões e o
   navegador. Desde 10/11/2026 também os outros processos da máquina (`--unshare-pid`): o
   agente não vê a lista nem a linha de comando deles.
3. **A rede continua:** o agente precisa da API do modelo, e o gancho de permissão fala com o Zé
   por `127.0.0.1`.
4. **Ligada sessão a sessão**, como o plano pede: vira o padrão depois de umas semanas sem
   quebrar nada. Sem o bubblewrap, a sessão protegida não é criada (a mensagem diz o que
   instalar); o modo antigo pelo SDK também não a aceita, porque não passaria pelo isolamento.
5. **O padrão desde 13/11/2026** (fecho da Fase B): sessão nova sem escolha nasce protegida
   quando a máquina permite, venha do painel, da voz, de Projetos 3D, do atendimento ou do
   autodesenvolvimento. A saída é por sessão: desmarcar "Protegida" no painel, ou pedir pela voz
   (`sessao_criar` com `protegida: false`). Sem o bubblewrap, o padrão não impede o trabalho: a
   sessão nasce sem proteção e o painel mostra "Indisponível"; pedir a protegida
   explicitamente continua dando erro. As sessões que já existiam guardam a escolha delas.
   O autodesenvolvimento grava a resposta falada fora do projeto: a sessão leva a pasta da
   manutenção como escrita extra (`Sessao.escrita`), e só ela. Conferido nesta máquina dentro
   do isolamento: `uv sync` do zero, `make lint`, o build do WaCalls e `git commit` funcionam;
   as dependências baixam de novo a cada início do agente, porque o cache da casa fica fora.

## Consequências

- Dentro da sessão protegida, `git push` por SSH e o `gh` não funcionam (as chaves ficam fora).
  É de propósito: publicar segue pelo usuário, como as regras das sessões já pediam.
- Não é um contêiner: o processo é do mesmo usuário e a rede é a mesma. Na VPS, o plano prevê um
  contêiner (fica para a Fase C).
- Falta: o cofre de segredos (o ambiente sem os segredos do
  Zé e o `/run/user` escondido entraram no [ADR 0075](0075-segredos-fora-do-agente.md); os
  segredos dos conectores ainda vão ao processo do agente).
