#!/usr/bin/env bash
# Рендер кусками по 900 кадров: прерванный рендер продолжается с места остановки.
set -euo pipefail
cd "$(dirname "$0")"
TOTAL=5490; STEP=900
BROWSER=${BROWSER:-/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell}
mkdir -p out/chunks
: > out/chunks/list.txt
for ((a=0; a<TOTAL; a+=STEP)); do
  b=$((a+STEP-1)); ((b>=TOTAL)) && b=$((TOTAL-1))
  f=out/chunks/part_$(printf %05d $a).mp4
  if [[ ! -s $f ]]; then
    npx remotion render src/index.ts AuraPromo "$f.tmp.mp4" --frames=$a-$b --muted \
      --browser-executable="$BROWSER" --concurrency=4 --log=error
    mv "$f.tmp.mp4" "$f"
  fi
  echo "done $b/$TOTAL"
  echo "file '$(basename $f)'" >> out/chunks/list.txt
done
# Звук — одним куском, чтобы не было щелчков на стыках.
[[ -s out/chunks/audio.wav ]] || npx remotion render src/index.ts AuraPromo out/chunks/audio.wav \
  --codec=wav --browser-executable="$BROWSER" --log=error
ffmpeg -y -loglevel error -f concat -safe 0 -i out/chunks/list.txt -i out/chunks/audio.wav \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest -movflags +faststart out/aura_promo.mp4
echo FINISHED
