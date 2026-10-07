#!/usr/bin/env bash
# Script behind docs/demo.gif. Runs the sample walk end to end into /tmp.
set -e
cd "$(dirname "$0")/.."
export HF_HUB_OFFLINE=1   # Whisper model already cached: no network needed
MODEL="${MODEL:-gemma4:e2b}"
p() { printf '\033[1;32m$\033[0m %s\n' "$*"; sleep 1; }
p "ls samples/walk-2026-10-08/memos"
ls -1 samples/walk-2026-10-08/memos
sleep 1
p "fieldmemo samples/walk-2026-10-08/memos --gpx samples/walk-2026-10-08/track.gpx --model $MODEL --out /tmp/journal --retranscribe"
fieldmemo samples/walk-2026-10-08/memos --gpx samples/walk-2026-10-08/track.gpx \
  --tz Europe/London --model "$MODEL" --out /tmp/journal --retranscribe
sleep 1
p "sed -n '5,18p' /tmp/journal/journal.md"
sed -n '5,18p' /tmp/journal/journal.md
sleep 3
