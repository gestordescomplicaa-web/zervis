#!/usr/bin/env bash
# Abre o painel do Zé numa janela própria (docs/plano-painel.md). O jarvisd serve a página em
# http://127.0.0.1:8795/. O perfil é o mesmo da janela imersiva (a aba Imersão embute o mesmo
# front: tema, calibração das mãos e câmera), separado do Chromium do dia a dia.
# Abrir o programa é a abertura do Zé (ADR 0078): `?abertura=1` leva à Imersão, que toca a música
# e apresenta o dia; o painel esquece o pedido, e recarregar não repete. A música toca sem um
# clique antes (`--autoplay-policy`), só nesta janela.
# O Zé como programa (ADR 0079): sem a partida automática (`systemctl --user enable zervis`),
# abrir liga o Zé e fechar a última janela dele o desliga: fechado, ele não escuta nem faz nada.
# Com a partida automática ligada, o Zé fica de pé como antes e a janela só abre e fecha.
#   PAINEL_DEPURACAO=9336 deploy/abrir-painel.sh   # só para conferir a janela por fora
set -euo pipefail
DADOS="${XDG_DATA_HOME:-$HOME/.local/share}"
PERFIL="$DADOS/zervis/navegador-painel"
mkdir -p "$PERFIL"
EXTRA=()
[[ -n "${PAINEL_DEPURACAO:-}" ]] && EXTRA=(--remote-debugging-port="$PAINEL_DEPURACAO")
PORTA="${ZERVIS_PAINEL_PORTA:-${JARVIS_PAINEL_PORTA:-8795}}"
ENDERECO="http://127.0.0.1:${PORTA}/?abertura=1"
SERVICO=zervis

# Programa: o serviço existe e não liga sozinho. Abrir o liga e espera o painel responder.
programa=0
if command -v systemctl >/dev/null && systemctl --user cat "$SERVICO" >/dev/null 2>&1; then
  systemctl --user is-enabled --quiet "$SERVICO" || programa=1
  systemctl --user is-active --quiet "$SERVICO" || systemctl --user start "$SERVICO"
  for _ in $(seq 1 120); do
    (exec 3<>"/dev/tcp/127.0.0.1/$PORTA") 2>/dev/null && break
    sleep 0.5
  done
fi

# As janelas do Zé: a do programa e a da Imersão que ele abre por voz (rosto/tela.py).
janela_aberta() {
  pgrep -f -- "--user-data-dir=$PERFIL" >/dev/null \
    || pgrep -f -- "--user-data-dir=$DADOS/zervis/janela" >/dev/null \
    || pgrep -f -- "--user-data-dir=$HOME/.local/share/barehands/browser" >/dev/null
}

# Uma atualização pelo painel (a unidade `zervis-atualizar`, zervis/versoes.py) ou um reinício
# do serviço ainda em curso. O teto é o da atualização mais longa (RODANDO_MAXIMO_S).
ESPERA_MAXIMA_S=$((15 * 60))
em_andamento() {
  systemctl --user is-active --quiet zervis-atualizar && return 0
  [[ -n "$(systemctl --user show -p Job --value "$SERVICO" 2>/dev/null)" ]] && return 0
  case "$(systemctl --user show -p ActiveState --value "$SERVICO" 2>/dev/null)" in
    activating | deactivating | reloading) return 0 ;;
  esac
  return 1
}

for navegador in chromium chromium-browser google-chrome google-chrome-stable; do
  if command -v "$navegador" >/dev/null; then
    comando=("$navegador" --user-data-dir="$PERFIL" --no-first-run --no-default-browser-check
      --autoplay-policy=no-user-gesture-required "${EXTRA[@]}" --app="$ENDERECO")
    if [[ $programa == 0 ]]; then
      exec "${comando[@]}"
    fi
    "${comando[@]}" || true
    # Com o perfil já aberto, o navegador entrega a janela à instância de pé e sai na hora:
    # o que vale é a última janela do Zé fechar. Fechada no meio de uma atualização ou de um
    # reinício, o Zé só desliga quando a troca termina: desligar antes fazia a atualização
    # achar que a versão nova não subiu e voltar para a anterior (11/11/2026). Uma janela
    # reaberta nesse meio-tempo mantém o Zé ligado.
    desde=$SECONDS
    while :; do
      if janela_aberta; then
        desde=$SECONDS
      elif ! em_andamento || ((SECONDS - desde >= ESPERA_MAXIMA_S)); then
        break
      fi
      sleep 2
    done
    systemctl --user stop "$SERVICO"
    exit 0
  fi
done
# No Ubuntu o navegador pode ser um snap, ou a pessoa pode usar Firefox como padrão. Sem saber
# quando a aba fecha, o Zé fica ligado (desliga com `systemctl --user stop zervis`).
exec xdg-open "$ENDERECO"
