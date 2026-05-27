#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-}"
WEBHOOK_URL="${2:-}"

if [[ -z "$ACTION" || ! "$ACTION" =~ ^(list|set|delete)$ ]]; then
  cat <<'USAGE'
Usage:
  MAX_BOT_TOKEN='<token>' bash scripts/max_webhook.sh list
  MAX_BOT_TOKEN='<token>' bash scripts/max_webhook.sh set [webhook_url]
  MAX_BOT_TOKEN='<token>' bash scripts/max_webhook.sh delete [webhook_url]

If webhook_url is omitted for set/delete, the script tries to read the current API Gateway domain from Terraform outputs and uses:
  https://<api_gateway_domain>/api/v1/bot/webhook

Examples:
  MAX_BOT_TOKEN='...' bash scripts/max_webhook.sh list
  MAX_BOT_TOKEN='...' bash scripts/max_webhook.sh set
  MAX_BOT_TOKEN='...' bash scripts/max_webhook.sh delete
USAGE
  exit 1
fi

: "${MAX_BOT_TOKEN:?MAX_BOT_TOKEN env var is required}"

if [[ "$ACTION" != "list" && -z "$WEBHOOK_URL" ]]; then
  if [[ -d "infra/terraform" ]]; then
    API_DOMAIN="$(cd infra/terraform && terraform output -raw api_gateway_domain 2>/dev/null || true)"
    if [[ -n "$API_DOMAIN" ]]; then
      WEBHOOK_URL="https://${API_DOMAIN}/api/v1/bot/webhook"
    fi
  fi
fi

API_BASE="https://platform-api.max.ru/subscriptions"

case "$ACTION" in
  list)
    curl -sS -X GET "$API_BASE" \
      -H "Authorization: ${MAX_BOT_TOKEN}"
    echo
    ;;

  set)
    [[ -n "$WEBHOOK_URL" ]] || { echo "webhook_url is required for set"; exit 1; }
    echo "Setting MAX webhook subscription to: $WEBHOOK_URL"
    curl -sS -X POST "$API_BASE" \
      -H "Authorization: ${MAX_BOT_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "{\"url\":\"${WEBHOOK_URL}\"}"
    echo
    ;;

  delete)
    [[ -n "$WEBHOOK_URL" ]] || { echo "webhook_url is required for delete"; exit 1; }
    echo "Deleting MAX webhook subscription: $WEBHOOK_URL"
    curl -sS -G -X DELETE "$API_BASE" \
      -H "Authorization: ${MAX_BOT_TOKEN}" \
      --data-urlencode "url=${WEBHOOK_URL}"
    echo
    ;;
esac
