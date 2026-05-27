#!/usr/bin/env bash
set -euo pipefail
env="${1:-}"; [[ "$env" == "dev" || "$env" == "prod" ]] || { echo "Usage: $0 <dev|prod>"; exit 1; }
read -rsp "Введите RegionCity API token: " REGIONCITY_API_TOKEN; echo
read -rsp "Введите MAX bot token: " MAX_BOT_TOKEN; echo
read -rsp "Введите ADMIN JWT secret (пусто=сгенерировать): " ADMIN_JWT_SECRET; echo
[[ -n "$ADMIN_JWT_SECRET" ]] || ADMIN_JWT_SECRET=$(python3 - <<PY
import secrets; print(secrets.token_urlsafe(48))
PY
)
mk(){
  local name="$1" key="$2" val="$3"
  local sid
  sid=$(yc lockbox secret get --name "$name" --format json 2>/dev/null | jq -r '.id' || true)
  [[ -n "$sid" && "$sid" != "null" ]] || sid=$(yc lockbox secret create --name "$name" --format json | jq -r '.id')
  yc lockbox secret add-version --id "$sid" --payload "[{\"key\":\"$key\",\"text_value\":\"$val\"}]" >/dev/null
  echo "$sid"
}
RID=$(mk "rn-${env}-regioncity-api-token" "REGIONCITY_API_TOKEN" "$REGIONCITY_API_TOKEN")
MID=$(mk "rn-${env}-max-bot-token" "MAX_BOT_TOKEN" "$MAX_BOT_TOKEN")
AID=$(mk "rn-${env}-admin-jwt-secret" "ADMIN_JWT_SECRET" "$ADMIN_JWT_SECRET")
mkdir -p ".local/${env}"
cat > ".local/${env}/secrets.env" <<ENV
REGIONCITY_SECRET_ID=$RID
MAX_BOT_SECRET_ID=$MID
ADMIN_JWT_SECRET_ID=$AID
ENV
echo "Lockbox secrets updated: .local/${env}/secrets.env"
