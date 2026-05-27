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

if [[ "$env" == "prod" ]]; then
  read -rp "This will empty buckets and destroy production resources. Type destroy-prod to continue: " confirmation
  [[ "$confirmation" == "destroy-prod" ]] || exit 1
fi

bash scripts/check_tools.sh

for deployment_file in ".local/${env}/backend.env" "infra/terraform/env/${env}.auto.tfvars" "infra/terraform/backend-${env}.hcl"; do
  [[ -f "$deployment_file" ]] || { echo "Missing deployment file: $deployment_file. Refusing to create resources during destroy."; exit 1; }
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

if [[ "$env" == "prod" ]]; then
  PROD_DESTROY_CONFIRMED=1 bash scripts/empty_storage_buckets.sh prod
else
  bash scripts/empty_storage_buckets.sh dev
fi

pushd infra/terraform >/dev/null
terraform init -input=false -reconfigure -backend-config="backend-${env}.hcl"
terraform validate
terraform destroy -input=false -auto-approve -var-file="env/${env}.auto.tfvars"
popd >/dev/null

echo "[destroy] destroyed Terraform-managed resources for env=$env"
