#!/usr/bin/env bash
set -euo pipefail

env="${1:-}"
[[ "$env" == "prod" ]] || { echo "Usage: $0 prod"; exit 1; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source scripts/yc_cli.sh

require_var() {
  local name="$1" value="${!1:-}"
  [[ -n "${value//[[:space:]]/}" ]] || { echo "Missing or empty environment variable: $name"; exit 1; }
}

require_var ADMIN_BOOTSTRAP_LOGIN
require_var ADMIN_BOOTSTRAP_PASSWORD

read -rp "This will create or update a production admin user. Type seed-prod-admin to continue: " confirmation
[[ "$confirmation" == "seed-prod-admin" ]] || exit 1

for deployment_file in ".local/${env}/backend.env" "infra/terraform/env/${env}.auto.tfvars" "infra/terraform/backend-${env}.hcl"; do
  [[ -f "$deployment_file" ]] || { echo "Missing deployment file: $deployment_file"; exit 1; }
done

bash scripts/check_tools.sh
# shellcheck disable=SC1090
source ".local/${env}/backend.env"

YDB_ENDPOINT="$(terraform -chdir=infra/terraform output -raw ydb_endpoint)"
YDB_DATABASE="$(terraform -chdir=infra/terraform output -raw ydb_database)"
require_var YDB_ENDPOINT
require_var YDB_DATABASE

bash backend/scripts/build_functions.sh "$env"
LOCAL_RUNTIME_PATH="$ROOT_DIR/.build/functions/admin_api"
[[ -d "$LOCAL_RUNTIME_PATH/ydb" ]] || {
  echo "Built function runtime is missing YDB dependencies: $LOCAL_RUNTIME_PATH"
  exit 1
}

export ENV="$env" YDB_ENDPOINT YDB_DATABASE PYTHONPATH="$LOCAL_RUNTIME_PATH"
YDB_ACCESS_TOKEN_CREDENTIALS="$(yc iam create-token)"
require_var YDB_ACCESS_TOKEN_CREDENTIALS
export YDB_ACCESS_TOKEN_CREDENTIALS

python3 backend/src/cli/seed_admin_user.py
echo "[admin] production admin user is ready"
