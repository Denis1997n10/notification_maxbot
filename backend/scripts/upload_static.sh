#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

for v in PUBLIC_BUCKET_NAME ADMIN_BUCKET_NAME; do
  [[ -n "${!v:-}" ]] || { echo "Missing env var: $v"; exit 1; }
done

(cd "$ROOT_DIR/frontend/public-site" && npm ci && npm run build >/dev/null)
(cd "$ROOT_DIR/frontend/admin-panel" && npm ci && npm run build >/dev/null)

yc storage cp --recursive "$ROOT_DIR/frontend/public-site/dist" "s3://$PUBLIC_BUCKET_NAME/"
yc storage cp --recursive "$ROOT_DIR/frontend/admin-panel/dist" "s3://$ADMIN_BUCKET_NAME/"

echo "[upload-static] uploaded to $PUBLIC_BUCKET_NAME and $ADMIN_BUCKET_NAME ($ENVIRONMENT)"
