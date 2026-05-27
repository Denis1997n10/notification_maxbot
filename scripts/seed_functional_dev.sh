#!/usr/bin/env bash
set -euo pipefail

export ENV="${ENV:-dev}"
export USE_MOCKS="${USE_MOCKS:-false}"

if [[ "$USE_MOCKS" == "true" ]]; then
  echo "[seed_functional_dev] USE_MOCKS=true; switch to real mode first" >&2
  exit 1
fi

python3 backend/src/cli/seed_functional_dev_data.py
