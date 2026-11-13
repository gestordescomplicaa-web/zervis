#!/bin/sh
# Instala no PC Linux e abre a configuração inicial, sem publicar o painel na internet.
# Use como usuário comum, no terminal da sessão gráfica: deploy/instalar-pc.sh
# Instala a última versão publicada; com --desenvolvimento, fica na master.
set -eu
exec "$(dirname "$0")/instalar-servidor.sh" --pc "$@"
