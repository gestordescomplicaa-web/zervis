#!/bin/sh
# Instala o Zé num servidor Linux sem tela nem áudio (VPS), como serviço do usuário que continua
# de pé depois de sair do SSH e sobe com a máquina (ADR 0034). Rode no repositório, como usuário
# comum, numa sessão SSH desse usuário:
#   deploy/instalar-servidor.sh
# Depois, do seu computador:
#   ssh -L 8795:127.0.0.1:8795 <usuário>@<servidor>    e abra http://localhost:8795
# Pelo túnel, o painel trata o acesso como o próprio computador: a configuração inicial e os
# ajustes de acesso funcionam. Guia completo: docs/vps.md.
set -eu
UV_VERSAO=0.11.32
PORTA=8795
REPO=$(cd "$(dirname "$0")/.." && pwd)
USUARIO=$(id -un)

falta() {
  echo "Falta: $*" >&2
  exit 1
}

# --- o que precisa existir antes -------------------------------------------------------------
[ "$(uname -s)" = Linux ] || falta "Linux."
[ "$(id -u)" -ne 0 ] || falta "um usuário comum. Como root, os agentes de código teriam acesso \
total ao servidor. Crie um (sudo adduser ze) e entre por SSH com ele."
glibc=$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}')
case "$glibc" in
  2.2[89]* | 2.[3-9]* | [3-9].*) ;;
  *) falta "glibc 2.28 ou mais nova (achei: ${glibc:-nenhuma}; Alpine não serve)." ;;
esac
for programa in git make curl; do
  command -v "$programa" >/dev/null || falta "$programa (sudo apt install $programa)."
done
command -v systemctl >/dev/null || falta "systemd."
systemctl --user show-environment >/dev/null 2>&1 || falta "o systemd do usuário. Entre por SSH \
direto como $USUARIO (su e sudo -u não abrem a sessão do usuário)."

# --- uv, dependências e modelos --------------------------------------------------------------
PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null; then
  echo "Instalando o uv $UV_VERSAO em ~/.local/bin"
  # Baixado antes de rodar: com `curl | sh`, um download que falha passa como sucesso.
  instalador=$(mktemp)
  curl -fLsS "https://astral.sh/uv/$UV_VERSAO/install.sh" -o "$instalador" \
    || falta "acesso a astral.sh para baixar o uv."
  sh "$instalador"
  rm -f "$instalador"
  command -v uv >/dev/null || falta "o uv (a instalação dele não terminou)."
fi
cd "$REPO"
# O autodesenvolvimento trabalha numa cópia isolada do código (git worktree) e precisa do Git.
# O código enviado como pacote (git archive + scp) chega sem o .git: aqui ele ganha um histórico
# local. Cada reinstalação registra o código novo como mais um commit, e nada sai da máquina.
GIT="git -c user.name=Zérvis -c user.email=zervis@localhost"
[ -e .git ] || $GIT init -q
if [ -n "$(git status --porcelain 2>/dev/null)" ] || ! git rev-parse -q --verify HEAD >/dev/null; then
  git add -A
  $GIT commit -qm "Zé instalado neste servidor" || echo "Aviso: o histórico Git local não foi criado; \
o autodesenvolvimento não vai abrir."
fi
uv sync --frozen
uv run python -m jarvis.preparar || echo "Aviso: os modelos de som não baixaram. O Zé sobe sem \
voz e baixa de novo no próximo início."
# Claude Code e Codex prontos, também como comandos no terminal (ADR 0035).
uv run python -m jarvis.cerebro.agentes_nativos

# --- serviço -----------------------------------------------------------------------------------
make instalar
# Sem linger, o systemd encerra os serviços do usuário quando a última sessão SSH fecha.
if ! loginctl enable-linger "$USUARIO" 2>/dev/null; then
  echo "Para o Zé continuar depois de sair do SSH, rode uma vez: sudo loginctl enable-linger $USUARIO"
fi
systemctl --user enable zervis
systemctl --user restart zervis

# --- conferência -------------------------------------------------------------------------------
printf "Esperando o painel"
i=0
until curl -s -o /dev/null "http://127.0.0.1:$PORTA/"; do
  i=$((i + 1))
  if [ $i -ge 120 ] || ! systemctl --user is-active --quiet zervis; then
    echo
    echo "O Zé não subiu. Últimas linhas do registro:" >&2
    journalctl --user -u zervis -n 30 --no-pager >&2 || true
    exit 1
  fi
  printf "."
  sleep 1
done
echo " pronto."

for opcional in node go; do
  if ! command -v "$opcional" >/dev/null; then
    case $opcional in
      node) echo "Opcional: Node, para o autodesenvolvimento conferir o painel (make check)." ;;
      go) echo "Opcional: Go, para o WhatsApp do atendimento." ;;
    esac
  fi
done
cat <<FIM

O Zé está rodando neste servidor (serviço zervis do usuário $USUARIO).
Do seu computador:
  ssh -L $PORTA:127.0.0.1:$PORTA $USUARIO@<endereço do servidor>
e abra http://localhost:$PORTA para a configuração inicial.
Registro: journalctl --user -u zervis -f
FIM
