#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
video="$repo_root/artifacts/ios/promo/paycheck-guardian-promo.mp4"

test -s "$video"

video_codec="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$video")"
width="$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of default=nw=1:nk=1 "$video")"
height="$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=nw=1:nk=1 "$video")"
frame_rate="$(ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate -of default=nw=1:nk=1 "$video")"
audio_codec="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=nw=1:nk=1 "$video")"
duration="$(ffprobe -v error -select_streams v:0 -show_entries stream=duration -of default=nw=1:nk=1 "$video")"
container_duration="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$video")"

test "$video_codec" = "h264"
test "$width" = "1920"
test "$height" = "1080"
test "$frame_rate" = "30/1"
test "$audio_codec" = "aac"
awk -v value="$duration" 'BEGIN {exit !(value >= 59.95 && value <= 60.05)}'
awk -v value="$container_duration" 'BEGIN {exit !(value >= 59.95 && value <= 60.10)}'

ffmpeg -v error -i "$video" -f null -

printf 'Video verified: H.264/AAC, %sx%s, %s fps, %.3f seconds, full decode clean.\n' \
  "$width" "$height" "$frame_rate" "$duration"
