#!/usr/bin/env bash
set -euo pipefail
env="${1:-}"; [[ "$env" == "dev" || "$env" == "prod" ]] || { echo "Usage: $0 <dev|prod>"; exit 1; }
cloud_id=$(yc config get cloud-id || true)
folder_id=$(yc config get folder-id || true)
[[ -n "$cloud_id" && -n "$folder_id" ]] || { echo "cloud-id/folder-id missing, run yc init"; exit 1; }
mkdir -p infra/terraform/env
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
public_origin = "https://${env}-public.example.com"
admin_origin = "https://${env}-admin.example.com"
public_site_url = "https://${env}-public.example.com"
admin_site_url = "https://${env}-admin.example.com"
regioncity_api_token_secret_id = "fill-after-bootstrap"
max_bot_token_secret_id = "fill-after-bootstrap"
admin_jwt_secret_id = "fill-after-bootstrap"
TF
echo "generated infra/terraform/env/${env}.auto.tfvars"
