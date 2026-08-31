#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
source_dir="$repo_root/artifacts/ios/screenshots"
target_dir="$repo_root/promo/public/screens"
mkdir -p "$target_dir"

for name in 01-welcome 02-verified-plan 03-evidence 04-simulated-approval 05-agent-trace; do
  test -f "$source_dir/$name.png"
  cp "$source_dir/$name.png" "$target_dir/$name.png"
done
