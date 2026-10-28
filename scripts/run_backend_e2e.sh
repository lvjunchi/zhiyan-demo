#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
rm -f data/e2e.db data/e2e.db-wal data/e2e.db-shm
python scripts/seed_catalog.py data/e2e.db
python scripts/seed_history.py data/e2e.db
export PYTHONPATH=backend
exec python -c "import uvicorn; from app.main import create_app; uvicorn.run(create_app('data/e2e.db'), host='127.0.0.1', port=8000, log_level='warning')"
