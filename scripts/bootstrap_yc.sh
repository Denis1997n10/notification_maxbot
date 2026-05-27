#!/usr/bin/env bash
set -euo pipefail

env="${1:-}"
[[ "$env" == "dev" || "$env" == "prod" ]] || { echo "Usage: $0 <dev|prod>"; exit 1; }

bash scripts/check_tools.sh
yc config get token >/dev/null 2>&1 || { echo "Run yc init first"; exit 1; }

cloud_id="${YC_CLOUD_ID:-$(yc config get cloud-id 2>/dev/null || true)}"
folder_id="${YC_FOLDER_ID:-$(yc config get folder-id 2>/dev/null || true)}"
[[ -n "$cloud_id" ]] || { echo "cloud_id is empty. Run: yc config set cloud-id <cloud_id>"; exit 1; }
[[ -n "$folder_id" ]] || { echo "folder_id is empty. Run: yc config set folder-id <folder_id>"; exit 1; }

mkdir -p ".local/${env}" infra/terraform/env

sa="sa-rn-${env}-deployer"
sa_id=$(yc iam service-account get --name "$sa" --format json 2>/dev/null | jq -r '.id' || true)
[[ -n "$sa_id" && "$sa_id" != "null" ]] || sa_id=$(yc iam service-account create --name "$sa" --folder-id "$folder_id" --format json | jq -r '.id')

# Temporary broad role for MVP bootstrap. Replace with least-privilege roles before production hardening.
yc resource-manager folder add-access-binding "$folder_id" --role editor --subject "serviceAccount:${sa_id}" >/dev/null || true

state_bucket="rn-${env}-terraform-state"
yc storage bucket create --name "$state_bucket" 2>/dev/null || true

AK_FILE=".local/${env}/s3-access-key.json"
if [[ ! -f "$AK_FILE" ]]; then
  yc iam access-key create --service-account-id "$sa_id" --format json > "$AK_FILE"
fi
AWS_ACCESS_KEY_ID=$(jq -r '.access_key.key_id' "$AK_FILE")
AWS_SECRET_ACCESS_KEY=$(jq -r '.secret' "$AK_FILE")

public_origin="${PUBLIC_ORIGIN:-http://localhost:5173}"
admin_origin="${ADMIN_ORIGIN:-http://localhost:5174}"
max_base="${MAX_API_BASE_URL:-https://platform-api.max.ru}"

if [[ "$env" == "dev" ]]; then
  function_use_mocks=true
  REGIONCITY_SECRET_ID="${REGIONCITY_SECRET_ID:-dev-regioncity-token-secret}"
  MAX_BOT_SECRET_ID="${MAX_BOT_SECRET_ID:-dev-max-bot-token-secret}"
  ADMIN_JWT_SECRET_ID="${ADMIN_JWT_SECRET_ID:-dev-admin-jwt-secret}"
else
  function_use_mocks=false
  bash scripts/create_lockbox_secrets.sh "$env"
  source ".local/${env}/secrets.env"
fi

cat > "infra/terraform/env/${env}.auto.tfvars" <<TF
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
max_bot_token_secret_id = "$MAX_BOT_SECRET_ID"
admin_jwt_secret_id = "$ADMIN_JWT_SECRET_ID"
function_use_mocks = $function_use_mocks
TF

cat > "infra/terraform/backend-${env}.hcl" <<HCL
bucket = "${state_bucket}"
key = "resident-notifications/${env}/terraform.tfstate"
region = "ru-central1"
endpoint = "https://storage.yandexcloud.net"
skip_region_validation = true
skip_credentials_validation = true
skip_metadata_api_check = true
HCL

cat > ".local/${env}/backend.env" <<ENV
export AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY"
export YC_CLOUD_ID="$cloud_id"
export YC_FOLDER_ID="$folder_id"
export YC_SERVICE_ACCOUNT_ID="$sa_id"
ENV

echo "Bootstrap completed. Generated: infra/terraform/env/${env}.auto.tfvars, infra/terraform/backend-${env}.hcl, .local/${env}/backend.env"
