#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
