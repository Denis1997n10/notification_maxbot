#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

for v in PUBLIC_BUCKET_NAME ADMIN_BUCKET_NAME API_BASE_URL; do
  [[ -n "${!v:-}" ]] || { echo "Missing env var: $v"; exit 1; }
done

(cd "$ROOT_DIR/frontend/public-site" && npm ci && VITE_PUBLIC_API_BASE_URL="$API_BASE_URL" npm run build >/dev/null)
(cd "$ROOT_DIR/frontend/admin-panel" && npm ci && VITE_ADMIN_API_BASE_URL="$API_BASE_URL" npm run build >/dev/null)

upload_site() {
  local dist_dir="$1" bucket="$2"
  local file relative_path content_type cache_control staged_uri
  local deployment_id
  deployment_id="$(date -u +%Y%m%dT%H%M%S%N)"

  while IFS= read -r -d '' file; do
    relative_path="${file#"$dist_dir"/}"
    content_type=""
    cache_control="public, max-age=31536000, immutable"
    case "$file" in
      *.html)
        content_type="text/html; charset=utf-8"
        cache_control="no-cache"
        # A direct cp can skip same-sized HTML whose hashed asset reference changed.
        staged_uri="s3://$bucket/.deploy/$deployment_id/$relative_path"
        yc storage s3 cp "$file" "$staged_uri" \
          --content-type "$content_type" \
          --cache-control "$cache_control" < /dev/null
        yc storage s3 cp "$staged_uri" "s3://$bucket/$relative_path" \
          --copy-props default < /dev/null
        yc storage s3 rm "$staged_uri" >/dev/null < /dev/null
        continue
        ;;
      *.js)
        content_type="application/javascript; charset=utf-8"
        ;;
      *.css)
        content_type="text/css; charset=utf-8"
        ;;
      *.json)
        content_type="application/json; charset=utf-8"
        ;;
      *.svg)
        content_type="image/svg+xml"
        ;;
      *.png)
        content_type="image/png"
        ;;
      *.jpg|*.jpeg)
        content_type="image/jpeg"
        ;;
    esac

    if [[ -n "$content_type" ]]; then
      yc storage s3 cp "$file" "s3://$bucket/$relative_path" \
        --content-type "$content_type" \
        --cache-control "$cache_control" < /dev/null
    else
      yc storage s3 cp "$file" "s3://$bucket/$relative_path" \
        --cache-control "$cache_control" < /dev/null
    fi
  done < <(find "$dist_dir" -type f -print0)
}

upload_site "$ROOT_DIR/frontend/public-site/dist" "$PUBLIC_BUCKET_NAME"
upload_site "$ROOT_DIR/frontend/admin-panel/dist" "$ADMIN_BUCKET_NAME"

echo "[upload-static] uploaded to $PUBLIC_BUCKET_NAME and $ADMIN_BUCKET_NAME ($ENVIRONMENT)"
