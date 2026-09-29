#!/usr/bin/env bash
# Build dist/store-readiness-audit.skill for uploading on claude.ai
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
rm -f dist/store-readiness-audit.skill
(cd skills && zip -rq ../dist/store-readiness-audit.skill store-readiness-audit \
  -x '*/__pycache__/*' '*.pyc' '*/.DS_Store')
echo "Built dist/store-readiness-audit.skill"
