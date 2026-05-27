#!/usr/bin/env bash
set -euo pipefail

env="${1:-prod}"
action="${2:-set}"
webhook_url="${3:-}"
[[ "$env" == "dev" || "$env" == "prod" ]] || { echo "Usage: $0 <dev|prod> [set|list|delete] [webhook_url]"; exit 1; }
[[ "$action" == "set" || "$action" == "list" || "$action" == "delete" ]] || { echo "Usage: $0 <dev|prod> [set|list|delete] [webhook_url]"; exit 1; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source scripts/yc_cli.sh

secrets_file=".local/${env}/secrets.env"
[[ -f "$secrets_file" ]] || { echo "Missing $secrets_file. Bootstrap real secrets first."; exit 1; }
# shellcheck disable=SC1090
source "$secrets_file"
backend_file=".local/${env}/backend.env"
[[ -f "$backend_file" ]] || { echo "Missing $backend_file. Bootstrap the environment first."; exit 1; }
# shellcheck disable=SC1090
source "$backend_file"

: "${MAX_BOT_SECRET_ID:?MAX_BOT_SECRET_ID is required in $secrets_file}"

read_lockbox_value() {
  local secret_id="$1" key="$2"
  yc lockbox payload get --id "$secret_id" --format json |
    jq -er --arg key "$key" '.entries[] | select(.key == $key) | .text_value | select(length > 0)'
}

if [[ "$env" == "prod" && "$action" != "list" && "${PROD_WEBHOOK_CONFIRMED:-}" != "1" ]]; then
  read -rp "This will change the production MAX webhook subscription. Type register-prod-webhook to continue: " confirmation
  [[ "$confirmation" == "register-prod-webhook" ]] || exit 1
fi

MAX_BOT_TOKEN="$(read_lockbox_value "$MAX_BOT_SECRET_ID" "MAX_BOT_TOKEN")"
export MAX_BOT_TOKEN

if [[ "$action" == "set" ]]; then
  : "${MAX_WEBHOOK_SECRET_ID:?MAX_WEBHOOK_SECRET_ID is required in $secrets_file}"
  MAX_WEBHOOK_SECRET="$(read_lockbox_value "$MAX_WEBHOOK_SECRET_ID" "MAX_WEBHOOK_SECRET")"
  export MAX_WEBHOOK_SECRET
fi

bash scripts/max_webhook.sh "$action" "$webhook_url"

unset MAX_BOT_TOKEN MAX_WEBHOOK_SECRET
