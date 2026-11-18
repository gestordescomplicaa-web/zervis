#!/usr/bin/env bash
# Junta os quadros e a trilha num MP4 (H.264 + AAC) e tira a capa.
# Uso: montar.sh <pasta de saída> <instante da capa em segundos>
# A pasta tem work/quadros/0000.jpg... e work/trilha.wav; saem brag.mp4 e brag.jpg. A capa (um
# quadro já assentado) vira também o quadro 0, para as redes mostrarem ela de miniatura; trocar
# o quadro 0, e não somar um, mantém a duração e o som no lugar.
set -euo pipefail
saida=$1
capa=$(printf '%04d' "$(awk -v t="$2" 'BEGIN { printf "%d", t * 30 }')")
cd "$saida"
cp "work/quadros/$capa.jpg" brag.jpg
rm -rf work/montagem && mkdir work/montagem
for f in work/quadros/*.jpg; do ln -s "../quadros/$(basename "$f")" "work/montagem/$(basename "$f")"; done
ln -sf "../quadros/$capa.jpg" work/montagem/0000.jpg
ffmpeg -loglevel error -y -framerate 30 -i work/montagem/%04d.jpg -i work/trilha.wav \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart \
  -c:a aac -b:a 192k -shortest brag.mp4
ffprobe -v error -count_frames -select_streams v:0 \
  -show_entries stream=width,height,nb_read_frames -of csv=p=0 brag.mp4
