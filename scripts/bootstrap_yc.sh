#!/usr/bin/env bash
set -euo pipefail

env="${1:-}"
[[ "$env" == "dev" || "$env" == "prod" ]] || { echo "Usage: $0 <dev|prod>"; exit 1; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source scripts/yc_cli.sh

require_non_empty() {
  local name="$1" value="$2"
  [[ -n "${value//[[:space:]]/}" ]] || { echo "$name must not be empty"; exit 1; }
}

if [[ "$env" == "prod" && "${PROD_CONFIRMED:-}" != "1" ]]; then
  read -rp "This will prepare production Yandex Cloud resources. Type bootstrap-prod to continue: " confirmation
  [[ "$confirmation" == "bootstrap-prod" ]] || exit 1
fi

bash scripts/check_tools.sh
yc config get token >/dev/null 2>&1 || { echo "Run yc init first"; exit 1; }

cloud_id="${YC_CLOUD_ID:-$(yc config get cloud-id 2>/dev/null || true)}"
folder_id="${YC_FOLDER_ID:-$(yc config get folder-id 2>/dev/null || true)}"
require_non_empty "cloud_id" "$cloud_id"
require_non_empty "folder_id" "$folder_id"

mkdir -p ".local/${env}" infra/terraform/env

sa="sa-rn-${env}-deployer"
sa_id="$(yc iam service-account get --name "$sa" --format json 2>/dev/null | jq -r '.id // empty' || true)"
if [[ -z "$sa_id" ]]; then
  sa_id="$(yc iam service-account create --name "$sa" --folder-id "$folder_id" --format json | jq -er '.id')"
fi
require_non_empty "service account id" "$sa_id"

# Bootstrap uses broad deployer rights; restrict this account before production hardening.
yc resource-manager folder add-access-binding "$folder_id" --role editor --subject "serviceAccount:${sa_id}" >/dev/null || true

state_bucket="rn-${env}-terraform-state"
yc storage bucket create --name "$state_bucket" 2>/dev/null || true

access_key_file=".local/${env}/s3-access-key.json"
if [[ ! -f "$access_key_file" ]]; then
  yc iam access-key create --service-account-id "$sa_id" --format json > "$access_key_file"
fi
AWS_ACCESS_KEY_ID="$(jq -er '.access_key.key_id | select(length > 0)' "$access_key_file")"
AWS_SECRET_ACCESS_KEY="$(jq -er '.secret | select(length > 0)' "$access_key_file")"

if [[ "$env" == "dev" ]]; then
  default_public_origin="http://localhost:5173"
  default_admin_origin="http://localhost:5174"
else
  default_public_origin="https://rn-public-${env}.website.yandexcloud.net"
  default_admin_origin="https://rn-admin-${env}.website.yandexcloud.net"
fi
public_origin="${PUBLIC_ORIGIN:-$default_public_origin}"
admin_origin="${ADMIN_ORIGIN:-$default_admin_origin}"
max_base="${MAX_API_BASE_URL:-https://platform-api.max.ru}"
require_non_empty "PUBLIC_ORIGIN" "$public_origin"
require_non_empty "ADMIN_ORIGIN" "$admin_origin"

if [[ "$env" == "dev" ]]; then
  function_use_mocks="${DEV_USE_MOCKS:-}"
  if [[ -z "$function_use_mocks" && -f "infra/terraform/env/dev.auto.tfvars" ]]; then
    function_use_mocks="$(awk -F'=' '/^[[:space:]]*function_use_mocks[[:space:]]*=/ { gsub(/[[:space:]]/, "", $2); print $2; exit }' infra/terraform/env/dev.auto.tfvars)"
  fi
  function_use_mocks="${function_use_mocks:-true}"
  [[ "$function_use_mocks" == "true" || "$function_use_mocks" == "false" ]] || {
    echo "DEV_USE_MOCKS must be true or false"
    exit 1
  }

  if [[ "$function_use_mocks" == "true" ]]; then
    REGIONCITY_SECRET_ID="dev-mock-regioncity-token"
    REGIONCITY_SECRET_VERSION_ID=""
    MAX_BOT_SECRET_ID="dev-mock-max-bot-token"
    MAX_BOT_SECRET_VERSION_ID=""
    ADMIN_JWT_SECRET_ID="dev-mock-admin-jwt-secret"
    ADMIN_JWT_SECRET_VERSION_ID=""
    MAX_WEBHOOK_SECRET_ID=""
    MAX_WEBHOOK_SECRET_VERSION_ID=""
  else
    [[ -f ".local/dev/secrets.env" ]] || {
      echo "Real dev mode needs Lockbox secret IDs. Run: bash scripts/create_lockbox_secrets.sh dev"
      exit 1
    }
    # shellcheck disable=SC1091
    source ".local/dev/secrets.env"
  fi
else
  function_use_mocks=false
  PROD_CONFIRMED=1 bash scripts/create_lockbox_secrets.sh "$env"
  # shellcheck disable=SC1090
  source ".local/${env}/secrets.env"
fi

require_non_empty "REGIONCITY_SECRET_ID" "${REGIONCITY_SECRET_ID:-}"
require_non_empty "MAX_BOT_SECRET_ID" "${MAX_BOT_SECRET_ID:-}"
require_non_empty "ADMIN_JWT_SECRET_ID" "${ADMIN_JWT_SECRET_ID:-}"
if [[ "$function_use_mocks" == "false" ]]; then
  require_non_empty "REGIONCITY_SECRET_VERSION_ID" "${REGIONCITY_SECRET_VERSION_ID:-}"
  require_non_empty "MAX_BOT_SECRET_VERSION_ID" "${MAX_BOT_SECRET_VERSION_ID:-}"
  require_non_empty "ADMIN_JWT_SECRET_VERSION_ID" "${ADMIN_JWT_SECRET_VERSION_ID:-}"
  require_non_empty "MAX_WEBHOOK_SECRET_ID" "${MAX_WEBHOOK_SECRET_ID:-}"
  require_non_empty "MAX_WEBHOOK_SECRET_VERSION_ID" "${MAX_WEBHOOK_SECRET_VERSION_ID:-}"
fi

cat > "infra/terraform/env/${env}.auto.tfvars" <<TFVARS
environment = "$env"
cloud_id = "$cloud_id"
folder_id = "$folder_id"
project_name = "resident-notifications"
resource_prefix = "rn"
ydb_name = "resident-notifications"
bucket_public_name = "rn-public-${env}"
bucket_admin_name = "rn-admin-${env}"
release_artifacts_bucket_name = "rn-release-${env}"
gateway_name = "resident-notifications-api"
public_origin = "$public_origin"
admin_origin = "$admin_origin"
public_site_url = "$public_origin"
admin_site_url = "$admin_origin"
max_api_base_url = "$max_base"
regioncity_api_token_secret_id = "$REGIONCITY_SECRET_ID"
regioncity_api_token_secret_version_id = "${REGIONCITY_SECRET_VERSION_ID:-}"
max_bot_token_secret_id = "$MAX_BOT_SECRET_ID"
max_bot_token_secret_version_id = "${MAX_BOT_SECRET_VERSION_ID:-}"
admin_jwt_secret_id = "$ADMIN_JWT_SECRET_ID"
admin_jwt_secret_version_id = "${ADMIN_JWT_SECRET_VERSION_ID:-}"
max_webhook_secret_id = "${MAX_WEBHOOK_SECRET_ID:-}"
max_webhook_secret_version_id = "${MAX_WEBHOOK_SECRET_VERSION_ID:-}"
function_use_mocks = $function_use_mocks
enable_polling_timer = false
TFVARS

cat > "infra/terraform/backend-${env}.hcl" <<BACKEND
bucket = "${state_bucket}"
key = "resident-notifications/${env}/terraform.tfstate"
region = "ru-central1"
endpoint = "https://storage.yandexcloud.net"
skip_region_validation = true
skip_credentials_validation = true
skip_metadata_api_check = true
BACKEND

cat > ".local/${env}/backend.env" <<BACKEND_ENV
export AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY"
export YC_CLOUD_ID="$cloud_id"
export YC_FOLDER_ID="$folder_id"
export YC_SERVICE_ACCOUNT_ID="$sa_id"
BACKEND_ENV

echo "[bootstrap] env=$env use_mocks=$function_use_mocks"
echo "[bootstrap] generated infra/terraform/env/${env}.auto.tfvars, infra/terraform/backend-${env}.hcl and .local/${env}/backend.env"
