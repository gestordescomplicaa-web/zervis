#!/bin/sh
# Instalação do zero (docs/06-qualidade.md): o último commit, extraído numa pasta limpa, com HOME e
# pastas XDG vazias, instala as dependências e passa no make check. Pega o que só funciona aqui
# porque sobrou na máquina: arquivo fora do Git, dependência instalada à mão, dado de quem usa.
# Os caches de download (uv, npm, Go) continuam os da máquina: baixar de novo não testa nada.
# Uso: deploy/check-instalacao.sh [commit]   (padrão: HEAD)
set -eu
REPO=$(git rev-parse --show-toplevel)
COMMIT=${1:-HEAD}
TEMP=$(mktemp -d "${TMPDIR:-/tmp}/zervis-instalacao.XXXXXX")
trap 'chmod -R u+w "$TEMP" 2>/dev/null; rm -rf "$TEMP"' EXIT INT TERM

export UV_CACHE_DIR="${UV_CACHE_DIR:-$(uv cache dir)}"
command -v npm >/dev/null && export npm_config_cache="${npm_config_cache:-$(npm config get cache)}"
if command -v go >/dev/null; then
  export GOMODCACHE="${GOMODCACHE:-$(go env GOMODCACHE)}" GOCACHE="${GOCACHE:-$(go env GOCACHE)}"
fi

mkdir -p "$TEMP/zervis" "$TEMP/home"
git -C "$REPO" archive "$COMMIT" | tar -x -C "$TEMP/zervis"
export HOME="$TEMP/home"
export XDG_CONFIG_HOME="$HOME/.config" XDG_DATA_HOME="$HOME/.local/share" XDG_STATE_HOME="$HOME/.local/state"
unset JARVIS_RAIZ JARVIS_PERFIL VIRTUAL_ENV

cd "$TEMP/zervis"
echo "instalação do zero: $(git -C "$REPO" rev-parse --short "$COMMIT") em $TEMP"
uv sync --frozen
# Com HOME vazio, os testes reais de áudio precisam dos modelos, como numa instalação nova.
# Sem essa preparação, ZE_SEM_PULOS=1 revela que a prova de features ONNX foi pulada.
uv run python -m jarvis.preparar
make check
echo "instalação do zero: aprovada"
