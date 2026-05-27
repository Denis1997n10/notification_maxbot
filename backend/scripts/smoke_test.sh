#!/usr/bin/env bash
set -euo pipefail
ENVIRONMENT="${1:-dev}"
: "${API_BASE_URL:?API_BASE_URL is required}"
check_non_5xx(){ local url="$1"; code=$(curl -sS -o /tmp/smoke.out -w "%{http_code}" "$url"); [[ "$code" != "5"* ]] || { echo "5xx for $url code=$code"; exit 1; }; }
check_non_5xx "$API_BASE_URL/api/v1/system/health"
check_non_5xx "$API_BASE_URL/api/v1/system/version"
check_non_5xx "$API_BASE_URL/api/v1/public/districts"
if [[ -n "${TEST_PUBLIC_CODE:-}" ]]; then check_non_5xx "$API_BASE_URL/api/v1/public/entrances/$TEST_PUBLIC_CODE"; else echo "skip TEST_PUBLIC_CODE"; fi
if [[ -n "${TEST_ADMIN_LOGIN:-}" && -n "${TEST_ADMIN_PASSWORD:-}" ]]; then
  code=$(curl -sS -o /tmp/smoke.admin -w "%{http_code}" -X POST "$API_BASE_URL/api/v1/admin/auth/login" -H 'Content-Type: application/json' -d "{\"login\":\"$TEST_ADMIN_LOGIN\",\"password\":\"$TEST_ADMIN_PASSWORD\"}")
  [[ "$code" != "5"* ]] || { echo "5xx for admin login"; exit 1; }
else echo "skip admin login"; fi
echo "smoke ok ($ENVIRONMENT)"
