#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
DIST_DIR="$ROOT_DIR/dist/functions"
BUILD_ROOT="$ROOT_DIR/.build/functions"
REQ_FILE="$BACKEND_DIR/requirements-dev.txt"

FUNCTIONS=(bot_webhook public_api admin_api regioncity_polling notification_sender)

echo "[build] env=$ENVIRONMENT root=$ROOT_DIR"
[[ -d "$BACKEND_DIR/src" ]] || { echo "backend/src missing"; exit 1; }
[[ -f "$REQ_FILE" ]] || { echo "requirements file missing: $REQ_FILE"; exit 1; }

rm -rf "$DIST_DIR" "$BUILD_ROOT"
mkdir -p "$DIST_DIR" "$BUILD_ROOT"

for fn in "${FUNCTIONS[@]}"; do
  echo "[build] packaging $fn"
  STAGE="$BUILD_ROOT/$fn"
  mkdir -p "$STAGE"

  # Copy package contents to ZIP root so imports like `from composition.container`
  # work in Yandex Cloud Functions without a custom PYTHONPATH.
  cp -R "$BACKEND_DIR/src/." "$STAGE/"
  cp "$BACKEND_DIR/functions/$fn/handler.py" "$STAGE/handler.py"

  python -m pip install -q -r "$REQ_FILE" -t "$STAGE" >/dev/null

  find "$STAGE" -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name 'tests' -o -name '.git' \) -prune -exec rm -rf {} +
  find "$STAGE" -type f \( -name '*.pyc' -o -name '.env' -o -name '.env.*' \) -delete

  (
    cd "$STAGE"
    find . -type f | LC_ALL=C sort > "$DIST_DIR/${fn}.manifest"
    zip -X -q -r "$DIST_DIR/${fn}.zip" .
  )
done

(
  cd "$DIST_DIR"
  sha256sum *.zip | sort > checksums.txt
)

echo "[build] artifacts in $DIST_DIR"
cat "$DIST_DIR/checksums.txt"
