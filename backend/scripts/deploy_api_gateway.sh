#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TPL="$ROOT_DIR/openapi/api-gateway.yaml.tftpl"
OUT="$ROOT_DIR/openapi/api-gateway.generated.yaml"

for v in PUBLIC_ORIGIN ADMIN_ORIGIN BOT_WEBHOOK_FUNCTION_ID PUBLIC_API_FUNCTION_ID ADMIN_API_FUNCTION_ID GATEWAY_SERVICE_ACCOUNT_ID; do
  [[ -n "${!v:-}" ]] || { echo "Missing env var: $v"; exit 1; }
done

python - <<PY
from pathlib import Path
from string import Template
p=Path('$TPL')
out=Template(p.read_text()).substitute(
  bot_webhook_function_id='${BOT_WEBHOOK_FUNCTION_ID}',
  public_api_function_id='${PUBLIC_API_FUNCTION_ID}',
  admin_api_function_id='${ADMIN_API_FUNCTION_ID}',
  gateway_service_account_id='${GATEWAY_SERVICE_ACCOUNT_ID}',
  public_origin='${PUBLIC_ORIGIN}',
  admin_origin='${ADMIN_ORIGIN}',
)
Path('$OUT').write_text(out)
print('rendered', '$OUT')
PY

GW_NAME="notification-api-$ENVIRONMENT"
if yc serverless api-gateway get --name "$GW_NAME" >/dev/null 2>&1; then
  yc serverless api-gateway update --name "$GW_NAME" --spec "$OUT" >/dev/null
else
  yc serverless api-gateway create --name "$GW_NAME" --spec "$OUT" >/dev/null
fi

echo "[deploy-gateway] deployed $GW_NAME"
