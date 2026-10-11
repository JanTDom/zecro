#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# This entry point is deliberately explicit: a missing or broken Supabase
# connection must fail at startup instead of silently creating SQLite data.
export ZECRO_LOAD_ENV_FILES="${ZECRO_LOAD_ENV_FILES:-true}"
export ZECRO_REQUIRE_REMOTE_DB="${ZECRO_REQUIRE_REMOTE_DB:-true}"
export ZECRO_REQUIRE_REMOTE_STORAGE="${ZECRO_REQUIRE_REMOTE_STORAGE:-true}"
export ZECRO_DATA_DIR="${ZECRO_DATA_DIR:-/tmp/zecro-backend}"
export ZECRO_CORS_ORIGINS="${ZECRO_CORS_ORIGINS:-https://zecro.pl,https://www.zecro.pl}"
export ZECRO_DEBUG="${ZECRO_DEBUG:-false}"

cd "${ROOT_DIR}"
exec python3 -m uvicorn backend.app.main:app \
  --host "${ZECRO_HOST:-127.0.0.1}" \
  --port "${ZECRO_PORT:-8000}"
