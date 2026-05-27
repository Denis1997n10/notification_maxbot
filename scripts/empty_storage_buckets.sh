#!/usr/bin/env bash
set -euo pipefail

env="${1:-}"
[[ "$env" == "dev" || "$env" == "prod" ]] || { echo "Usage: $0 <dev|prod>"; exit 1; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source scripts/yc_cli.sh

if [[ "$env" == "prod" && "${PROD_DESTROY_CONFIRMED:-}" != "1" ]]; then
  read -rp "This will delete all objects from production buckets. Type empty-prod-buckets to continue: " confirmation
  [[ "$confirmation" == "empty-prod-buckets" ]] || exit 1
fi

tfvars="infra/terraform/env/${env}.auto.tfvars"
[[ -f "$tfvars" ]] || { echo "Missing $tfvars. A deployed environment configuration is required."; exit 1; }
[[ -f ".local/${env}/backend.env" ]] || { echo "Missing .local/${env}/backend.env"; exit 1; }

# shellcheck disable=SC1090
source ".local/${env}/backend.env"

read_tfvar() {
  local name="$1"
  awk -F'=' -v key="$name" '$1 ~ "^[[:space:]]*" key "[[:space:]]*$" { gsub(/[[:space:]\"]/, "", $2); print $2; exit }' "$tfvars"
}

buckets=(
  "$(read_tfvar bucket_public_name)"
  "$(read_tfvar bucket_admin_name)"
  "$(read_tfvar release_artifacts_bucket_name)"
)

for bucket in "${buckets[@]}"; do
  [[ -n "$bucket" ]] || { echo "Bucket name is empty in $tfvars; refusing cleanup."; exit 1; }
  yc storage bucket get --name "$bucket" >/dev/null || {
    echo "Cannot access bucket $bucket; refusing terraform destroy."
    exit 1
  }
  echo "[cleanup] emptying s3://$bucket/"
  yc storage s3 rm --recursive "s3://$bucket/"
done

echo "[cleanup] storage buckets are empty for env=$env"
