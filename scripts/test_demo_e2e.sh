#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

SOURCE_DB="${DEMO_DB_SOURCE:-data/demo.db}"
E2E_DB="${DEMO_DB_E2E:-data/demo-e2e.db}"

if [[ ! -f "$SOURCE_DB" ]]; then
  echo "演示数据库不存在：$SOURCE_DB" >&2
  echo "请先执行：python scripts/build_demo.py data/demo.db --reset" >&2
  exit 1
fi

hash_before="$(sha256sum "$SOURCE_DB" | awk '{print $1}')"
rm -f "$E2E_DB" "$E2E_DB-wal" "$E2E_DB-shm"
cp "$SOURCE_DB" "$E2E_DB"

cleanup() {
  rm -f "$E2E_DB" "$E2E_DB-wal" "$E2E_DB-shm"
}
trap cleanup EXIT

export DEMO_DB="$E2E_DB"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-0}"

cd frontend
npx playwright test --config playwright.demo.config.ts "$@"
cd ..

hash_after="$(sha256sum "$SOURCE_DB" | awk '{print $1}')"
if [[ "$hash_before" != "$hash_after" ]]; then
  echo "错误：演示库在走查期间被修改：$SOURCE_DB" >&2
  exit 1
fi
echo "演示库副本走查完成，原库 SHA-256 未变：$hash_after"
