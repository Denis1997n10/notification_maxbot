#!/usr/bin/env bash
set -euo pipefail
env="${1:-}"; [[ "$env" == "dev" || "$env" == "prod" ]] || { echo "Usage: $0 <dev|prod>"; exit 1; }
if [[ "$env" == "prod" ]]; then read -rp "Type deploy-prod to continue: " c; [[ "$c" == "deploy-prod" ]] || exit 1; fi
bash scripts/check_tools.sh
source ".local/${env}/backend.env"
export YC_TOKEN_FILE="$YC_SERVICE_ACCOUNT_KEY_FILE"
bash backend/scripts/build_functions.sh "$env"
cd infra/terraform
terraform init -backend-config="backend-${env}.hcl"
terraform validate
terraform plan -var-file="env/${env}.auto.tfvars"
read -rp "Confirm terraform apply? [yes/no]: " ok; [[ "$ok" == "yes" ]]
terraform apply -auto-approve -var-file="env/${env}.auto.tfvars"
API_DOMAIN=$(terraform output -raw api_gateway_domain)
cd ../..
python3 backend/scripts/apply_ydb_migrations.py
bash backend/scripts/deploy_functions.sh "$env"
export PUBLIC_ORIGIN=$(grep '^public_origin' infra/terraform/env/${env}.auto.tfvars | cut -d'"' -f2)
export ADMIN_ORIGIN=$(grep '^admin_origin' infra/terraform/env/${env}.auto.tfvars | cut -d'"' -f2)
export BOT_WEBHOOK_FUNCTION_ID=$(yc serverless function get --name "bot-webhook-${env}" --format json | jq -r .id)
export PUBLIC_API_FUNCTION_ID=$(yc serverless function get --name "public-api-${env}" --format json | jq -r .id)
export ADMIN_API_FUNCTION_ID=$(yc serverless function get --name "admin-api-${env}" --format json | jq -r .id)
bash backend/scripts/deploy_api_gateway.sh "$env"
export PUBLIC_BUCKET_NAME=$(grep '^bucket_public_name' infra/terraform/env/${env}.auto.tfvars | cut -d'"' -f2)
export ADMIN_BUCKET_NAME=$(grep '^bucket_admin_name' infra/terraform/env/${env}.auto.tfvars | cut -d'"' -f2)
bash backend/scripts/upload_static.sh "$env"
if [[ "$env" == "dev" ]]; then ENV=local python3 backend/src/cli/seed_demo_data.py || true; fi
export API_BASE_URL="https://${API_DOMAIN}"
bash backend/scripts/smoke_test.sh "$env"
echo "API Gateway: https://${API_DOMAIN}"
echo "Public site: $PUBLIC_ORIGIN"
echo "Admin site: $ADMIN_ORIGIN"
echo "Health: https://${API_DOMAIN}/api/v1/system/health"
