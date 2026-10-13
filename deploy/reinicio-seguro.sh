#!/bin/sh
# Reinício seguro do Zé (serviço zervis) (modo manutenção). Roda FORA do jarvisd, por systemd-run, porque
# reinicia o próprio serviço: reinicia, espera o batimento novo e, se a versão nova não subir,
# guarda o que mudou (stash e um commit de volta) e volta ao commit bom, sem apagar nada.
# Uso: reinicio-seguro.sh <repo> <commit bom> <pasta da manutenção>
set -u
REPO=$1
BOM=$2
PASTA=$3
STATUS="${XDG_STATE_HOME:-$HOME/.local/state}/zervis/status.json"

pid_de() { /usr/bin/python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("pid",""))' "$STATUS" 2>/dev/null; }
batida_de() { /usr/bin/python3 -c 'import json,sys; print(int(json.load(open(sys.argv[1])).get("batimento",0)))' "$STATUS" 2>/dev/null; }

subiu() {
  antes=$1
  desde=$2
  i=0
  while [ $i -lt 40 ]; do
    sleep 1
    i=$((i + 1))
    pid=$(pid_de)
    batida=$(batida_de)
    if systemctl --user is-active --quiet zervis && [ -n "$pid" ] && [ "$pid" != "$antes" ] \
       && [ "${batida:-0}" -gt "$desde" ]; then
      return 0
    fi
  done
  return 1
}

dizer() { printf '{"resultado": "%s", "bom": "%s", "em": %s}\n' "$1" "$BOM" "$(date +%s)" > "$PASTA/reinicio.json"; }

sleep 5   # o JARVIS termina de dizer que vai se reiniciar
antes=$(pid_de)
agora=$(date +%s)
systemctl --user restart zervis
if subiu "$antes" "$agora"; then
  dizer ok
  exit 0
fi

# A versão nova não subiu: guarda tudo e volta ao commit bom com um commit novo (nada se perde).
novo=$(git -C "$REPO" rev-parse --short HEAD)
git -C "$REPO" stash push --include-untracked -m "manutencao: versao $novo nao subiu" >/dev/null 2>&1
# Um commit novo com a árvore exata do commit bom (arquivos criados pela versão nova saem também);
# o histórico da versão que não subiu continua lá, para corrigir depois.
volta=$(git -C "$REPO" commit-tree "$BOM^{tree}" -p HEAD \
  -m "Volta automática ao $BOM: a versão $novo não subiu (modo manutenção)")
git -C "$REPO" reset -q --hard "$volta"
dizer voltou
antes=$(pid_de)
agora=$(date +%s)
systemctl --user reset-failed zervis 2>/dev/null  # a versão que não subiu pode ter batido o limite
systemctl --user restart zervis
subiu "$antes" "$agora"
