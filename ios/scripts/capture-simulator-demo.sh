#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
project="$repo_root/ios/PaycheckGuardian.xcodeproj"
output_dir="$repo_root/artifacts/ios/screenshots"
destination="${IOS_SIMULATOR_DESTINATION:-platform=iOS Simulator,name=iPhone 17 Pro}"
capture_dir="$(mktemp -d /tmp/paycheck-guardian-ios-capture.XXXXXX)"
trap 'rm -rf "$capture_dir"' EXIT

mkdir -p "$output_dir" "$capture_dir/export"
xcodebuild \
  -project "$project" \
  -scheme PaycheckGuardian \
  -destination "$destination" \
  -derivedDataPath "$capture_dir/DerivedData" \
  -resultBundlePath "$capture_dir/Capture.xcresult" \
  -only-testing:PaycheckGuardianUITests/PaycheckGuardianUITests/testCaptureHackathonScreens \
  test \
  CODE_SIGNING_ALLOWED=NO

xcrun xcresulttool export attachments \
  --path "$capture_dir/Capture.xcresult" \
  --output-path "$capture_dir/export"

while IFS=$'\t' read -r exported suggested; do
  clean_name="$(printf '%s' "$suggested" | sed -E 's/_[0-9]+_[A-F0-9-]+\.png$/.png/')"
  cp "$capture_dir/export/$exported" "$output_dir/$clean_name"
done < <(jq -r '.[].attachments[] | [.exportedFileName, .suggestedHumanReadableName] | @tsv' "$capture_dir/export/manifest.json")

printf 'Simulator screenshots written to %s\n' "$output_dir"

