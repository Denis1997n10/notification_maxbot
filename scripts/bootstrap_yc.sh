#!/usr/bin/env bash
set -euo pipefail
env="${1:-}"; [[ "$env" == "dev" || "$env" == "prod" ]] || { echo "Usage: $0 <dev|prod>"; exit 1; }
bash scripts/check_tools.sh
if ! yc config get token >/dev/null 2>&1; then echo "Run yc init first"; exit 1; fi
cloud_id=$(yc config get cloud-id || true); folder_id=$(yc config get folder-id || true)
[[ -n "$cloud_id" ]] || read -rp "cloud_id: " cloud_id
[[ -n "$folder_id" ]] || read -rp "folder_id: " folder_id
sa="sa-rn-${env}-deployer"
sa_id=$(yc iam service-account get --name "$sa" --format json 2>/dev/null | jq -r '.id' || true)
[[ -n "$sa_id" && "$sa_id" != "null" ]] || sa_id=$(yc iam service-account create --name "$sa" --folder-id "$folder_id" --format json | jq -r '.id')
yc resource-manager folder add-access-binding "$folder_id" --role editor --subject "serviceAccount:${sa_id}" >/dev/null || true
state_bucket="rn-${env}-terraform-state"
yc storage bucket create --name "$state_bucket" 2>/dev/null || true
sak_json=".local/${env}/sa-key.json"; mkdir -p ".local/${env}"
[[ -f "$sak_json" ]] || yc iam key create --service-account-id "$sa_id" --output "$sak_json"
read -rp "MAX API base URL [https://botapi.max.ru]: " max_base; max_base=${max_base:-https://botapi.max.ru}
bash scripts/create_lockbox_secrets.sh "$env"
source ".local/${env}/secrets.env"
bash scripts/generate_tfvars.sh "$env"
sed -i "s/regioncity_api_token_secret_id = \".*\"/regioncity_api_token_secret_id = \"$REGIONCITY_SECRET_ID\"/" "infra/terraform/env/${env}.auto.tfvars"
sed -i "s/max_bot_token_secret_id = \".*\"/max_bot_token_secret_id = \"$MAX_BOT_SECRET_ID\"/" "infra/terraform/env/${env}.auto.tfvars"
sed -i "s/admin_jwt_secret_id = \".*\"/admin_jwt_secret_id = \"$ADMIN_JWT_SECRET_ID\"/" "infra/terraform/env/${env}.auto.tfvars"
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
export YC_CLOUD_ID="$cloud_id"
export YC_FOLDER_ID="$folder_id"
export YC_SERVICE_ACCOUNT_ID="$sa_id"
export YC_SERVICE_ACCOUNT_KEY_FILE="$(pwd)/$sak_json"
export TF_BACKEND_CONFIG="$(pwd)/infra/terraform/backend-${env}.hcl"
export MAX_API_BASE_URL="$max_base"
ENV
echo "Bootstrap completed. Next: ./scripts/deploy_all.sh ${env}"
