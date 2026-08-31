#!/bin/bash
set -euo pipefail

audio_dir="$(cd "$(dirname "$0")/../public" && pwd)/audio"

for name in narration soundtrack; do
  file="$audio_dir/$name.wav"
  test -s "$file"
  codec="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$file")"
  rate="$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate -of default=nw=1:nk=1 "$file")"
  channels="$(ffprobe -v error -select_streams a:0 -show_entries stream=channels -of default=nw=1:nk=1 "$file")"
  duration="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$file")"
  test "$codec" = "pcm_s16le"
  test "$rate" = "48000"
  test "$channels" = "2"
  awk -v value="$duration" 'BEGIN {exit !(value >= 59.99 && value <= 60.01)}'
  test "$(wc -c < "$file")" -gt 100000
done

printf 'Audio verified: narration and soundtrack are 48 kHz stereo PCM, 60 seconds.\n'
