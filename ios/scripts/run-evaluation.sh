#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "$0")/../.." && pwd -P)"

swift run \
  --package-path "$repository_root/ios/Packages/PaycheckGuardianCore" \
  PaycheckGuardianEvaluation \
  --output-directory "$repository_root/artifacts/ios/evaluation"
