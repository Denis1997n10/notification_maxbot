#!/usr/bin/env bash
set -euo pipefail
ENVIRONMENT="${1:-dev}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REL="$ROOT/release"
DIST="$ROOT/dist/functions"
COMMIT=$(git -C "$ROOT" rev-parse --short HEAD)
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
VERSION=${APP_VERSION:-0.1.0}

rm -rf "$REL" && mkdir -p "$REL"
bash "$ROOT/backend/scripts/build_functions.sh" "$ENVIRONMENT"
(cd "$ROOT/frontend/public-site" && npm ci && npm run build >/dev/null)
(cd "$ROOT/frontend/admin-panel" && npm ci && npm run build >/dev/null)

cp -R "$DIST" "$REL/functions"
cp -R "$ROOT/frontend/public-site/dist" "$REL/public-site-dist"
cp -R "$ROOT/frontend/admin-panel/dist" "$REL/admin-panel-dist"
cp "$ROOT/openapi/api-gateway.yaml.tftpl" "$REL/"
cp -R "$ROOT/infra/terraform" "$REL/terraform"
cp -R "$ROOT/backend/migrations" "$REL/migrations"
tar --exclude='.git' --exclude='*.env' --exclude='node_modules' --exclude='release' -czf "$REL/source.tar.gz" -C "$ROOT" .

echo "version=$VERSION" > "$REL/version.txt"
echo "build_time_utc=$TS" >> "$REL/version.txt"
echo "commit=$COMMIT" >> "$REL/version.txt"

bash "$ROOT/scripts/generate_sbom.sh" "$REL/dependency-inventory.txt"
cat > "$REL/release-notes.md" <<RN
# Release notes
- Version: $VERSION
- Commit: $COMMIT
- Built at: $TS
RN

(cd "$REL" && find . -type f | sort | xargs sha256sum > checksums.txt)
echo "release built at $REL"
