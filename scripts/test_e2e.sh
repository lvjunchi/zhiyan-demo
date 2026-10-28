#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../frontend"
export PLAYWRIGHT_BROWSERS_PATH=0
exec npx playwright test "$@"
