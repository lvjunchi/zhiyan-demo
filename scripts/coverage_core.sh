#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=backend PYTHONIOENCODING=utf-8 python -m pytest backend/tests \
  -o addopts='' \
  --cov=backend/app \
  --cov-branch \
  --cov-report=term-missing \
  --cov-report=json:coverage-core.json \
  --cov-fail-under=80
python scripts/check_core_coverage.py coverage-core.json
