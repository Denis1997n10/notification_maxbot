CREATE TABLE IF NOT EXISTS public_page_cache (
  cache_key Utf8,
  payload_json Utf8,
  expires_at Timestamp,
  PRIMARY KEY (cache_key)
);
