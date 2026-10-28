#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
DB_PATH="${DEMO_DB:-data/demo.db}"
if [[ ! -f "$DB_PATH" ]]; then
  echo "演示数据库不存在：$DB_PATH" >&2
  echo "请先执行：python scripts/build_demo.py data/demo.db --reset" >&2
  exit 1
fi
export PYTHONPATH=backend
export PYTHONIOENCODING=utf-8
export DEMO_DB="$DB_PATH"
exec python -c "import os, uvicorn; from app.main import create_app; uvicorn.run(create_app(os.environ['DEMO_DB']), host='127.0.0.1', port=8000, log_level='warning')"
