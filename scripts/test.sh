#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONIOENCODING=utf-8 python -m pytest "$@"
