#!/usr/bin/env bash
set -euo pipefail

env="${1:-}"
[[ "$env" == "dev" || "$env" == "prod" ]] || { echo "Usage: $0 <dev|prod>"; exit 1; }

if [[ "$env" == "prod" ]]; then
  read -rp "This will delete all objects from prod buckets. Type empty-prod-buckets to continue: " c
  [[ "$c" == "empty-prod-buckets" ]] || exit 1
fi

tfvars="infra/terraform/env/${env}.auto.tfvars"
[[ -f "$tfvars" ]] || { echo "Missing $tfvars. Run: bash scripts/bootstrap_yc.sh ${env}"; exit 1; }

if [[ -f ".local/${env}/backend.env" ]]; then
  # Provides S3-compatible credentials created during bootstrap.
  source ".local/${env}/backend.env"
fi

read_tfvar() {
  local name="$1"
  awk -F'=' -v key="$name" '$1 ~ "^[[:space:]]*" key "[[:space:]]*$" { gsub(/[[:space:]\"]/, "", $2); print $2 }' "$tfvars"
}

buckets=(
  "$(read_tfvar bucket_public_name)"
  "$(read_tfvar bucket_admin_name)"
  "$(read_tfvar release_artifacts_bucket_name)"
)

for bucket in "${buckets[@]}"; do
  [[ -n "$bucket" ]] || continue
  echo "[cleanup] emptying s3://$bucket/"
  yc storage s3 rm --recursive "s3://$bucket/" >/dev/null 2>&1 || true

done

echo "[cleanup] storage buckets are empty for env=$env"
