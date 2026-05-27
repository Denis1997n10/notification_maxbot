#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

for v in PUBLIC_BUCKET_NAME ADMIN_BUCKET_NAME API_BASE_URL; do
  [[ -n "${!v:-}" ]] || { echo "Missing env var: $v"; exit 1; }
done

(cd "$ROOT_DIR/frontend/public-site" && npm ci && VITE_PUBLIC_API_BASE_URL="$API_BASE_URL" npm run build >/dev/null)
(cd "$ROOT_DIR/frontend/admin-panel" && npm ci && VITE_ADMIN_API_BASE_URL="$API_BASE_URL" npm run build >/dev/null)

# Yandex CLI exposes Object Storage copy through the S3 subcommand.
yc storage s3 cp --recursive "$ROOT_DIR/frontend/public-site/dist/" "s3://$PUBLIC_BUCKET_NAME/"
yc storage s3 cp --recursive "$ROOT_DIR/frontend/admin-panel/dist/" "s3://$ADMIN_BUCKET_NAME/"

echo "[upload-static] uploaded to $PUBLIC_BUCKET_NAME and $ADMIN_BUCKET_NAME ($ENVIRONMENT)"
