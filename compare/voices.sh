#!/usr/bin/env bash
# Synthesise the Spanish lines of one Short with Piper (es_AR-daniela-high, CC BY-SA 4.0) into DIR/<hash>.wav
set -euo pipefail
A=$1; B=$2; SEED=$3; DIR=$4
mkdir -p "$DIR" ~/.cache/piper
M=~/.cache/piper/es_AR-daniela-high.onnx
base=https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_AR/daniela/high/es_AR-daniela-high
[ -s "$M" ] || curl -sSfL -o "$M" "$base.onnx"
[ -s "$M.json" ] || curl -sSfL -o "$M.json" "$base.onnx.json"
python3 compare/render.py "$A" "$B" --seed "$SEED" --out x --lines | while IFS=$'\t' read -r h line; do
  echo "$line" | python3 -m piper -m "$M" -f "$DIR/$h.wav" --length-scale 1.05 >/dev/null 2>&1 || echo "voice failed: $line"
done
ls "$DIR" | wc -l
