#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export ZECRO_DATA_DIR="${ZECRO_DATA_DIR:-${ROOT_DIR}/backend/data}"
export ZECRO_CORS_ORIGINS="${ZECRO_CORS_ORIGINS:-https://zecro.pl,https://www.zecro.pl,http://localhost:5173,http://127.0.0.1:5173}"
export ZECRO_DEBUG="${ZECRO_DEBUG:-false}"

cd "${ROOT_DIR}"
exec python3 -m uvicorn backend.app.main:app \
  --host "${ZECRO_HOST:-127.0.0.1}" \
  --port "${ZECRO_PORT:-8000}"
