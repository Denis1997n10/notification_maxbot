#!/usr/bin/env bash
set -euo pipefail

env="${1:-}"
[[ "$env" == "dev" || "$env" == "prod" ]] || { echo "Usage: $0 <dev|prod>"; exit 1; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source scripts/yc_cli.sh

if [[ "$env" == "prod" && "${PROD_CONFIRMED:-}" != "1" ]]; then
  read -rp "This will update production Lockbox secrets. Type update-prod-secrets to continue: " confirmation
  [[ "$confirmation" == "update-prod-secrets" ]] || exit 1
fi

read -rsp "Enter RegionCity API token: " REGIONCITY_API_TOKEN; echo
read -rsp "Enter MAX bot token: " MAX_BOT_TOKEN; echo
read -rsp "Enter ADMIN JWT secret (empty generates a value): " ADMIN_JWT_SECRET; echo
read -rsp "Enter MAX webhook secret (required again when registering the webhook): " MAX_WEBHOOK_SECRET; echo
[[ -n "$REGIONCITY_API_TOKEN" ]] || { echo "RegionCity API token must not be empty"; exit 1; }
[[ -n "$MAX_BOT_TOKEN" ]] || { echo "MAX bot token must not be empty"; exit 1; }
[[ -n "$MAX_WEBHOOK_SECRET" ]] || { echo "MAX webhook secret must not be empty"; exit 1; }
[[ -n "$ADMIN_JWT_SECRET" ]] || ADMIN_JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"

put_secret() {
  local name="$1" key="$2" value="$3" secret_id version_id payload
  secret_id="$(yc lockbox secret get --name "$name" --format json 2>/dev/null | jq -r '.id // empty' || true)"
  if [[ -z "$secret_id" ]]; then
    secret_id="$(yc lockbox secret create --name "$name" --format json | jq -er '.id')"
  fi
  payload="$(jq -cn --arg key "$key" --arg value "$value" '[{key: $key, text_value: $value}]')"
  version_id="$(yc lockbox secret add-version --id "$secret_id" --payload "$payload" --format json | jq -er '.id')"
  printf '%s|%s' "$secret_id" "$version_id"
}

IFS='|' read -r REGIONCITY_SECRET_ID REGIONCITY_SECRET_VERSION_ID <<< "$(put_secret "rn-${env}-regioncity-api-token" "REGIONCITY_API_TOKEN" "$REGIONCITY_API_TOKEN")"
IFS='|' read -r MAX_BOT_SECRET_ID MAX_BOT_SECRET_VERSION_ID <<< "$(put_secret "rn-${env}-max-bot-token" "MAX_BOT_TOKEN" "$MAX_BOT_TOKEN")"
IFS='|' read -r ADMIN_JWT_SECRET_ID ADMIN_JWT_SECRET_VERSION_ID <<< "$(put_secret "rn-${env}-admin-jwt-secret" "ADMIN_JWT_SECRET" "$ADMIN_JWT_SECRET")"
IFS='|' read -r MAX_WEBHOOK_SECRET_ID MAX_WEBHOOK_SECRET_VERSION_ID <<< "$(put_secret "rn-${env}-max-webhook-secret" "MAX_WEBHOOK_SECRET" "$MAX_WEBHOOK_SECRET")"

mkdir -p ".local/${env}"
cat > ".local/${env}/secrets.env" <<SECRETS
REGIONCITY_SECRET_ID="$REGIONCITY_SECRET_ID"
REGIONCITY_SECRET_VERSION_ID="$REGIONCITY_SECRET_VERSION_ID"
MAX_BOT_SECRET_ID="$MAX_BOT_SECRET_ID"
MAX_BOT_SECRET_VERSION_ID="$MAX_BOT_SECRET_VERSION_ID"
ADMIN_JWT_SECRET_ID="$ADMIN_JWT_SECRET_ID"
ADMIN_JWT_SECRET_VERSION_ID="$ADMIN_JWT_SECRET_VERSION_ID"
MAX_WEBHOOK_SECRET_ID="$MAX_WEBHOOK_SECRET_ID"
MAX_WEBHOOK_SECRET_VERSION_ID="$MAX_WEBHOOK_SECRET_VERSION_ID"
SECRETS

echo "[lockbox] updated secret ID mapping in .local/${env}/secrets.env"
