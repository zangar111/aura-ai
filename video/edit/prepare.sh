#!/usr/bin/env bash
# Копирует шикі материал и озвучку в public/ перед studio/render.
set -euo pipefail
cd "$(dirname "$0")"
cp ../raw/out/*.mp4 ../raw/out/logo*.png public/
cp ../voice/adi/full.mp3 public/voice.mp3
