#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
package_dir="$repo_root/ios/Packages/PaycheckGuardianCore"
project="$repo_root/ios/PaycheckGuardian.xcodeproj"
destination="${IOS_SIMULATOR_DESTINATION:-platform=iOS Simulator,name=iPhone 17 Pro}"
derived_data="$(mktemp -d /tmp/paycheck-guardian-ios-tests.XXXXXX)"
trap 'rm -rf "$derived_data"' EXIT

(cd "$package_dir" && swift test)
xcodebuild \
  -project "$project" \
  -scheme PaycheckGuardian \
  -destination "$destination" \
  -derivedDataPath "$derived_data" \
  test \
  CODE_SIGNING_ALLOWED=NO

