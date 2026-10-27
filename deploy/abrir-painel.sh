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
ENDERECO="http://127.0.0.1:${ZERVIS_PAINEL_PORTA:-${JARVIS_PAINEL_PORTA:-8795}}/"
for navegador in chromium chromium-browser google-chrome google-chrome-stable; do
  if command -v "$navegador" >/dev/null; then
    exec "$navegador" --user-data-dir="$PERFIL" --no-first-run --no-default-browser-check \
      "${EXTRA[@]}" --app="$ENDERECO"
  fi
done
# No Ubuntu o navegador pode ser um snap, ou a pessoa pode usar Firefox como padrão.
exec xdg-open "$ENDERECO"
