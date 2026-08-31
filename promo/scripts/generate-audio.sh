#!/bin/bash
set -euo pipefail

promo_root="$(cd "$(dirname "$0")/.." && pwd)"
audio_dir="$promo_root/public/audio"
work_dir="$(mktemp -d /tmp/paycheck-guardian-promo-audio.XXXXXX)"
trap 'rm -rf "$work_dir"' EXIT
mkdir -p "$audio_dir"

if say -v '?' | awk '$1 == "Samantha" && $2 == "en_US" {found=1} END {exit !found}'; then
  voice="Samantha"
else
  voice="$(say -v '?' | awk '$2 == "en_US" {print $1; exit}')"
fi
test -n "$voice"

say -v "$voice" -r 145 -f "$promo_root/audio/narration.txt" -o "$work_dir/narration.aiff"
ffmpeg -hide_banner -loglevel error -y \
  -i "$work_dir/narration.aiff" \
  -af "loudnorm=I=-16:TP=-1.5:LRA=10,aresample=48000,apad=whole_len=2880000,atrim=end_sample=2880000,asetpts=N/SR/TB" \
  -ar 48000 -ac 2 -c:a pcm_s16le \
  "$audio_dir/narration.wav"

ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "sine=frequency=110:sample_rate=48000:duration=60" \
  -f lavfi -i "sine=frequency=220:sample_rate=48000:duration=60" \
  -f lavfi -i "sine=frequency=440:sample_rate=48000:duration=60" \
  -f lavfi -i "anoisesrc=color=pink:amplitude=0.03:sample_rate=48000:duration=60" \
  -filter_complex "[0:a]volume=0.14,tremolo=f=0.25:d=0.32[a0];[1:a]volume=0.055,tremolo=f=1:d=0.70[a1];[2:a]volume=0.032,tremolo=f=2:d=0.92[a2];[3:a]highpass=f=4200,lowpass=f=9000,volume=0.024,tremolo=f=2:d=0.96[a3];[a0][a1][a2][a3]amix=inputs=4:normalize=0,afade=t=in:st=0:d=2,afade=t=out:st=56:d=4,loudnorm=I=-27:TP=-3:LRA=7,atrim=0:60[out]" \
  -map "[out]" -ar 48000 -ac 2 -c:a pcm_s16le \
  "$audio_dir/soundtrack.wav"

printf 'Generated narration with voice %s and an original 60-second soundtrack.\n' "$voice"
