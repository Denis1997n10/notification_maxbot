#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="$ROOT_DIR/dist/functions"

FUNCTIONS=(bot_webhook public_api admin_api regioncity_polling notification_sender)

for v in YC_FOLDER_ID YC_FUNCTION_SA_ID; do
  [[ -n "${!v:-}" ]] || { echo "Missing env var: $v"; exit 1; }
done

for fn in "${FUNCTIONS[@]}"; do
  ZIP="$DIST_DIR/${fn}.zip"
  [[ -f "$ZIP" ]] || { echo "Artifact missing: $ZIP"; exit 1; }
  NAME="${fn//_/-}-$ENVIRONMENT"

  if ! yc serverless function get --name "$NAME" >/dev/null 2>&1; then
    yc serverless function create --name "$NAME" --folder-id "$YC_FOLDER_ID" >/dev/null
  fi

  yc serverless function version create \
    --function-name "$NAME" \
    --runtime python312 \
    --entrypoint handler.handler \
    --memory 256m \
    --execution-timeout 60s \
    --service-account-id "$YC_FUNCTION_SA_ID" \
    --source-path "$ZIP" >/dev/null

  echo "[deploy-functions] deployed $NAME from $ZIP"
done
