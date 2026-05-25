#!/usr/bin/env bash
set -euo pipefail
ENVIRONMENT="${1:-dev}"
: "${API_BASE_URL:?API_BASE_URL is required}"

echo "[smoke] env=$ENVIRONMENT api=$API_BASE_URL"
code=$(curl -sS -o /tmp/public_districts.json -w "%{http_code}" "$API_BASE_URL/api/v1/public/districts")
[[ "$code" != "5"* ]] || { echo "public/districts failed with $code"; exit 1; }

if [[ -n "${TEST_PUBLIC_CODE:-}" ]]; then
  code=$(curl -sS -o /tmp/public_entrance.json -w "%{http_code}" "$API_BASE_URL/api/v1/public/entrances/$TEST_PUBLIC_CODE")
  [[ "$code" != "5"* ]] || { echo "public entrance failed with $code"; exit 1; }
else
  echo "[smoke] skip public entrance: TEST_PUBLIC_CODE not set"
fi

if [[ -n "${TEST_ADMIN_LOGIN:-}" && -n "${TEST_ADMIN_PASSWORD:-}" ]]; then
  code=$(curl -sS -o /tmp/admin_login.json -w "%{http_code}" -X POST "$API_BASE_URL/api/v1/admin/auth/login" -H 'Content-Type: application/json' -d "{\"login\":\"$TEST_ADMIN_LOGIN\",\"password\":\"$TEST_ADMIN_PASSWORD\"}")
  [[ "$code" != "5"* ]] || { echo "admin login failed with $code"; exit 1; }
else
  echo "[smoke] skip admin login: TEST_ADMIN_LOGIN/TEST_ADMIN_PASSWORD not set"
fi

echo "[smoke] done"
