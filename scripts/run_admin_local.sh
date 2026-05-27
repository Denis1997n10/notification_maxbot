#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DOMAIN="$(cd "$ROOT_DIR/infra/terraform" && terraform output -raw api_gateway_domain 2>/dev/null || true)"

[[ -n "$API_DOMAIN" ]] || { echo "Cannot read api_gateway_domain from Terraform outputs. Run deploy first."; exit 1; }

cd "$ROOT_DIR/frontend/admin-panel"
npm ci

echo "Admin UI: http://localhost:5174"
echo "API target through Vite proxy: https://${API_DOMAIN}"
VITE_PROXY_TARGET="https://${API_DOMAIN}" VITE_ADMIN_API_BASE_URL="" npm run dev -- --host 0.0.0.0 --port 5174
