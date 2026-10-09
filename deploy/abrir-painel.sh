#!/usr/bin/env bash
# Abre o painel do Zé numa janela própria (docs/plano-painel.md). O jarvisd serve a página em
# http://127.0.0.1:8795/. O perfil é o mesmo da janela imersiva (a aba Imersão embute o mesmo
# front: tema, calibração das mãos e câmera), separado do Chromium do dia a dia.
#   PAINEL_DEPURACAO=9336 deploy/abrir-painel.sh   # só para conferir a janela por fora
set -euo pipefail
PERFIL="${XDG_DATA_HOME:-$HOME/.local/share}/zervis/navegador-painel"
mkdir -p "$PERFIL"
EXTRA=()
[[ -n "${PAINEL_DEPURACAO:-}" ]] && EXTRA=(--remote-debugging-port="$PAINEL_DEPURACAO")
setsid chromium --user-data-dir="$PERFIL" --no-first-run --no-default-browser-check \
  "${EXTRA[@]}" --app="http://127.0.0.1:${JARVIS_PAINEL_PORTA:-8795}/" >/dev/null 2>&1 &
