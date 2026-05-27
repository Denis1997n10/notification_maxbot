#!/usr/bin/env bash
set -euo pipefail

env="${1:-}"
[[ "$env" == "dev" || "$env" == "prod" ]] || { echo "Usage: $0 <dev|prod>"; exit 1; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source scripts/yc_cli.sh

require_var() {
  local name="$1" value="${!1:-}"
  [[ -n "${value//[[:space:]]/}" ]] || { echo "Missing or empty environment variable: $name"; exit 1; }
}

if [[ "$env" == "dev" ]]; then
  # A dev deploy is intentionally a one-command flow; mock secrets are the default.
  bash scripts/bootstrap_yc.sh dev
else
  read -rp "This will deploy production resources. Type deploy-prod to continue: " confirmation
  [[ "$confirmation" == "deploy-prod" ]] || exit 1
  if [[ -n "${ADMIN_BOOTSTRAP_LOGIN:-}" || -n "${ADMIN_BOOTSTRAP_PASSWORD:-}" ]]; then
    require_var ADMIN_BOOTSTRAP_LOGIN
    require_var ADMIN_BOOTSTRAP_PASSWORD
  fi
  if [[ ! -f ".local/prod/backend.env" || ! -f "infra/terraform/env/prod.auto.tfvars" || ! -f "infra/terraform/backend-prod.hcl" ]]; then
    PROD_CONFIRMED=1 bash scripts/bootstrap_yc.sh prod
  fi
fi

bash scripts/check_tools.sh

for deployment_file in ".local/${env}/backend.env" "infra/terraform/env/${env}.auto.tfvars" "infra/terraform/backend-${env}.hcl"; do
  [[ -f "$deployment_file" ]] || { echo "Missing deployment file: $deployment_file"; exit 1; }
done

# shellcheck disable=SC1090
source ".local/${env}/backend.env"
require_var AWS_ACCESS_KEY_ID
require_var AWS_SECRET_ACCESS_KEY
require_var YC_CLOUD_ID
require_var YC_FOLDER_ID

if [[ -z "${YC_TOKEN:-}" ]]; then
  YC_TOKEN="$(yc config get token 2>/dev/null || true)"
fi
require_var YC_TOKEN
export YC_TOKEN TF_INPUT=0 TF_IN_AUTOMATION=1

bash backend/scripts/build_functions.sh "$env"

pushd infra/terraform >/dev/null
terraform init -input=false -reconfigure -backend-config="backend-${env}.hcl"
terraform validate
plan_file=".terraform/${env}.tfplan"
terraform plan -input=false -out="$plan_file" -var-file="env/${env}.auto.tfvars"
terraform apply -input=false "$plan_file"

API_DOMAIN="$(terraform output -raw api_gateway_domain)"
YDB_ENDPOINT="$(terraform output -raw ydb_endpoint)"
YDB_DATABASE="$(terraform output -raw ydb_database)"
PUBLIC_SITE_URL="$(terraform output -raw public_site_url)"
ADMIN_SITE_URL="$(terraform output -raw admin_site_url)"
PUBLIC_BUCKET_NAME="$(terraform output -raw public_bucket_name)"
ADMIN_BUCKET_NAME="$(terraform output -raw admin_bucket_name)"
popd >/dev/null

require_var API_DOMAIN
require_var YDB_ENDPOINT
require_var YDB_DATABASE
require_var PUBLIC_BUCKET_NAME
require_var ADMIN_BUCKET_NAME

export PUBLIC_BUCKET_NAME ADMIN_BUCKET_NAME
export ENV="$env" YDB_ENDPOINT YDB_DATABASE
LOCAL_RUNTIME_PATH="$ROOT_DIR/.build/functions/admin_api"
[[ -d "$LOCAL_RUNTIME_PATH/ydb" ]] || {
  echo "Built function runtime is missing YDB dependencies: $LOCAL_RUNTIME_PATH"
  exit 1
}
export PYTHONPATH="$LOCAL_RUNTIME_PATH"
export API_BASE_URL="https://${API_DOMAIN}"
YDB_ACCESS_TOKEN_CREDENTIALS="$(yc iam create-token)"
require_var YDB_ACCESS_TOKEN_CREDENTIALS
export YDB_ACCESS_TOKEN_CREDENTIALS

python3 backend/scripts/apply_ydb_migrations.py
bash backend/scripts/upload_static.sh "$env"

if [[ "$env" == "dev" ]]; then
  ENV=local PYTHONPATH="$ROOT_DIR/backend/src" python3 backend/src/cli/seed_demo_data.py || true
elif [[ -n "${ADMIN_BOOTSTRAP_LOGIN:-}" || -n "${ADMIN_BOOTSTRAP_PASSWORD:-}" ]]; then
  require_var ADMIN_BOOTSTRAP_LOGIN
  require_var ADMIN_BOOTSTRAP_PASSWORD
  ENV="$env" python3 backend/src/cli/seed_admin_user.py
fi

bash backend/scripts/smoke_test.sh "$env"
echo "API Gateway: https://${API_DOMAIN}"
echo "Public site: $PUBLIC_SITE_URL"
echo "Admin site: $ADMIN_SITE_URL"
echo "Health: https://${API_DOMAIN}/api/v1/system/health"
