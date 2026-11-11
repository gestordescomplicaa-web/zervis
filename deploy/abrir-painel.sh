#!/usr/bin/env bash
# Abre o painel do Zé numa janela própria (docs/plano-painel.md). O jarvisd serve a página em
# http://127.0.0.1:8795/. O perfil é o mesmo da janela imersiva (a aba Imersão embute o mesmo
# front: tema, calibração das mãos e câmera), separado do Chromium do dia a dia.
# Abrir o programa é a abertura do Zé (ADR 0078): `?abertura=1` leva à Imersão, que toca a música
# e apresenta o dia; o painel esquece o pedido, e recarregar não repete. A música toca sem um
# clique antes (`--autoplay-policy`), só nesta janela.
#   PAINEL_DEPURACAO=9336 deploy/abrir-painel.sh   # só para conferir a janela por fora
set -euo pipefail
PERFIL="${XDG_DATA_HOME:-$HOME/.local/share}/zervis/navegador-painel"
mkdir -p "$PERFIL"
EXTRA=()
[[ -n "${PAINEL_DEPURACAO:-}" ]] && EXTRA=(--remote-debugging-port="$PAINEL_DEPURACAO")
ENDERECO="http://127.0.0.1:${ZERVIS_PAINEL_PORTA:-${JARVIS_PAINEL_PORTA:-8795}}/?abertura=1"
for navegador in chromium chromium-browser google-chrome google-chrome-stable; do
  if command -v "$navegador" >/dev/null; then
    exec "$navegador" --user-data-dir="$PERFIL" --no-first-run --no-default-browser-check \
      --autoplay-policy=no-user-gesture-required "${EXTRA[@]}" --app="$ENDERECO"
  fi
done
# No Ubuntu o navegador pode ser um snap, ou a pessoa pode usar Firefox como padrão.
exec xdg-open "$ENDERECO"
