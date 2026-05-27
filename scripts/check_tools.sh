#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/yc_cli.sh"

missing=0
check(){ if ! command -v "$1" >/dev/null 2>&1; then echo "[MISSING] $1"; missing=1; fi }
for t in yc terraform python3 pip node npm git zip jq; do check "$t"; done
if [[ "$missing" -eq 1 ]]; then
  cat <<MSG
Установите отсутствующие инструменты и повторите:
- yc: https://yandex.cloud/ru/docs/cli/quickstart
- terraform: https://developer.hashicorp.com/terraform/install
- node/npm: https://nodejs.org
MSG
  exit 1
fi
echo "[ok] all required tools found"
