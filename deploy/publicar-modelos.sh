#!/bin/sh
# Publica os modelos de som do Zé numa release do GitHub, para o primeiro início não depender do
# HuggingFace (ADR 0034, ponto 13). Rode onde os modelos já existem (o seu PC, depois de o Zé ter
# subido uma vez), com o CLI `gh` logado:
#   deploy/publicar-modelos.sh <dono/repositório> [etiqueta]
# Exemplo: deploy/publicar-modelos.sh minha-conta/zervis-modelos modelos-1
#
# Antes de subir, cada arquivo é conferido contra a impressão digital (SHA-256) fixa em
# jarvis/preparar.py: só vai o que o projeto já testou. O repositório precisa ser PÚBLICO para o
# download funcionar sem login; num privado o Zé cai para a fonte original. Depois de publicar,
# o endereço impresso no fim vai em ESPELHO (jarvis/preparar.py) ou em ZE_MODELOS_URL.
#   MODELOS=<pasta>      onde estão os modelos (padrão: a pasta de dados do Zé)
#   ZE_SIMULAR=1         confere tudo e mostra o que faria, sem publicar
set -eu

REPO=${1:-}
TAG=${2:-modelos-1}
[ -n "$REPO" ] || {
  echo "Uso: $0 <dono/repositório> [etiqueta]" >&2
  exit 2
}
case "$REPO" in */*) ;; *)
  echo "O repositório é <dono>/<nome>, como minha-conta/zervis-modelos." >&2
  exit 2
  ;;
esac

falta() {
  echo "Falta: $*" >&2
  exit 1
}

AQUI=$(cd "$(dirname "$0")/.." && pwd)
PASTA=${MODELOS:-${XDG_DATA_HOME:-$HOME/.local/share}/zervis/modelos}
command -v gh >/dev/null || falta "o CLI gh (https://cli.github.com), logado com gh auth login."
command -v uv >/dev/null || falta "o uv (https://docs.astral.sh/uv)."
[ -d "$PASTA" ] || falta "a pasta de modelos $PASTA. Suba o Zé uma vez (ou rode python -m jarvis.preparar)."

TEMP=$(mktemp -d)
trap 'rm -rf "$TEMP"' EXIT INT TERM

# --- conferir contra as impressões digitais do código ----------------------------------------
(cd "$AQUI" && uv run --frozen python -m jarvis.preparar --manifesto) >"$TEMP/SHA256SUMS"
if ! (cd "$PASTA" && sha256sum -c "$TEMP/SHA256SUMS"); then
  falta "modelos íntegros em $PASTA: algum falta ou não bate com o SHA-256 do projeto (acima)."
fi

cat >"$TEMP/LICENCAS.md" <<'FIM'
# Modelos de som do Zérvis: origem e licenças

Arquivos idênticos aos originais, conferidos pelo SHA-256 em `SHA256SUMS`. Estão aqui só para o
Zérvis não depender de uma única fonte na primeira instalação.

| Arquivo | Origem | Licença |
|---|---|---|
| `pt_BR-cadu-medium.onnx`, `pt_BR-cadu-medium.onnx.json` | Voz Cadu do Piper, dataset Cadu 1.0 (github.com/OHF-Voice/voice-datasets), Open Home Foundation | CC0-1.0 |
| `silero_vad.onnx` | Silero VAD, distribuído com o openWakeWord (github.com/snakers4/silero-vad), Silero Team | MIT |
| `melspectrogram.onnx`, `embedding_model.onnx` | openWakeWord (github.com/dscripka/openWakeWord), David Scripka; conversão do `speech_embedding` do Google | Apache-2.0 |
| `smart-turn-v3.2-cpu.onnx` | Smart Turn v3.2 (github.com/pipecat-ai/smart-turn), Daily | BSD-2-Clause |

Textos das licenças: https://creativecommons.org/publicdomain/zero/1.0/ ·
https://opensource.org/license/mit · https://www.apache.org/licenses/LICENSE-2.0 ·
https://opensource.org/license/bsd-2-clause
FIM

# --- publicar ---------------------------------------------------------------------------------
ARQUIVOS=$(awk '{print $2}' "$TEMP/SHA256SUMS")
set --
for nome in $ARQUIVOS; do set -- "$@" "$PASTA/$nome"; done
set -- "$@" "$TEMP/SHA256SUMS" "$TEMP/LICENCAS.md"

visibilidade=$(gh repo view "$REPO" --json visibility -q .visibility 2>/dev/null) \
  || falta "acesso ao repositório $REPO (ele existe? gh auth status)."
[ "$visibilidade" = PUBLIC ] \
  || echo "Aviso: $REPO é $visibilidade. Sem login, ninguém baixa dele; o Zé usaria a fonte original."

if [ -n "${ZE_SIMULAR:-}" ]; then
  echo "Simulação: publicaria $# arquivos na release $TAG de $REPO:"
  printf '  %s\n' "$@"
else
  # Repositório recém-criado, sem nenhum commit: o GitHub não cria a etiqueta da release ("HTTP
  # 422: Repository is empty"). Um README inicial dá o primeiro commit.
  if ! consulta=$(gh api "repos/$REPO/commits?per_page=1" 2>&1); then
    case "$consulta" in
      *mpty*)
        echo "Repositório vazio: criando o README inicial."
        texto=$(printf '# Zérvis: modelos de som\n\nEspelho dos modelos de som e da voz Cadu usados pelo Zérvis. Os arquivos estão na release; origem e licenças em LICENCAS.md.\n' | base64 | tr -d '\n')
        gh api -X PUT "repos/$REPO/contents/README.md" -f message="README inicial" \
          -f content="$texto" >/dev/null || falta "criar o README em $REPO."
        ;;
      *) falta "ler $REPO: $consulta" ;;
    esac
  fi
  # Rascunho que uma tentativa anterior deixou: a busca por etiqueta não o enxerga, e uma nova
  # release ficaria ao lado dele.
  for id in $(gh api "repos/$REPO/releases" --jq ".[] | select(.draft and .tag_name==\"$TAG\") | .id"); do
    echo "Apagando o rascunho $id de uma tentativa anterior."
    gh api -X DELETE "repos/$REPO/releases/$id" >/dev/null
  done
  if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
    gh release upload "$TAG" --repo "$REPO" --clobber "$@"
  else
    gh release create "$TAG" --repo "$REPO" --title "Modelos de som do Zé" \
      --notes "Modelos de som e a voz Cadu. Origem e licenças em LICENCAS.md; impressões digitais em SHA256SUMS." "$@"
  fi
fi

echo
echo "Endereço do espelho (vai em ESPELHO, em jarvis/preparar.py, ou em ZE_MODELOS_URL):"
echo "  https://github.com/$REPO/releases/download/$TAG"
