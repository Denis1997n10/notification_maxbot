#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/release/dependency-inventory.txt}"
mkdir -p "$(dirname "$OUT")"
{
  echo "# Python deps"
  cat "$ROOT/backend/requirements-dev.txt"
  echo
  echo "# npm public-site"
  python - <<PY
import json, pathlib
for p in ['frontend/public-site/package.json','frontend/admin-panel/package.json']:
 d=json.loads(pathlib.Path('$ROOT',p).read_text());
 print('##',p); print(d.get('dependencies',{})); print(d.get('devDependencies',{}))
PY
  echo
  echo "# Terraform providers"
  grep -n "required_providers" -A20 "$ROOT/infra/terraform/main.tf" || true
} > "$OUT"
