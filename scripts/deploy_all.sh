#!/usr/bin/env bash
set -euo pipefail
env="${1:-}"; [[ "$env" == "dev" || "$env" == "prod" ]] || { echo "Usage: $0 <dev|prod>"; exit 1; }
if [[ "$env" == "prod" ]]; then read -rp "Type deploy-prod to continue: " c; [[ "$c" == "deploy-prod" ]] || exit 1; fi
bash scripts/check_tools.sh
source ".local/${env}/backend.env"

if [[ -z "${YC_TOKEN:-}" ]]; then
  YC_TOKEN="$(yc config get token 2>/dev/null || true)"
fi
[[ -n "${YC_TOKEN:-}" ]] || { echo "YC_TOKEN is empty. Run yc init and try again."; exit 1; }
export YC_TOKEN

bash backend/scripts/build_functions.sh "$env"
cd infra/terraform
terraform init -backend-config="backend-${env}.hcl"
terraform validate
terraform plan -var-file="env/${env}.auto.tfvars"
read -rp "Confirm terraform apply? [yes/no]: " ok; [[ "$ok" == "yes" ]]
terraform apply -auto-approve -var-file="env/${env}.auto.tfvars"
API_DOMAIN=$(terraform output -raw api_gateway_domain)
YDB_ENDPOINT=$(terraform output -raw ydb_endpoint)
YDB_DATABASE=$(terraform output -raw ydb_database)
PUBLIC_SITE_URL=$(terraform output -raw public_site_url)
ADMIN_SITE_URL=$(terraform output -raw admin_site_url)
PUBLIC_BUCKET_NAME=$(terraform output -raw public_bucket_name)
ADMIN_BUCKET_NAME=$(terraform output -raw admin_bucket_name)
cd ../..
[[ -n "$YDB_ENDPOINT" && -n "$YDB_DATABASE" ]] || { echo "YDB outputs are empty"; exit 1; }
[[ -n "$PUBLIC_BUCKET_NAME" && -n "$ADMIN_BUCKET_NAME" ]] || { echo "Bucket outputs are empty"; exit 1; }
export PUBLIC_BUCKET_NAME ADMIN_BUCKET_NAME
export ENV="$env" YDB_ENDPOINT YDB_DATABASE
export PYTHONPATH="$PWD/backend/src"
python3 backend/scripts/apply_ydb_migrations.py
# functions managed by terraform
bash backend/scripts/upload_static.sh "$env"
if [[ "$env" == "dev" ]]; then ENV=local PYTHONPATH="$PWD/backend/src" python3 backend/src/cli/seed_demo_data.py || true; fi
export API_BASE_URL="https://${API_DOMAIN}"
bash backend/scripts/smoke_test.sh "$env"
echo "API Gateway: https://${API_DOMAIN}"
echo "Public site: $PUBLIC_SITE_URL"
echo "Admin site: $ADMIN_SITE_URL"
echo "Health: https://${API_DOMAIN}/api/v1/system/health"
