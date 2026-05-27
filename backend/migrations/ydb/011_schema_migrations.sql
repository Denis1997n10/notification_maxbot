CREATE TABLE IF NOT EXISTS schema_migrations (
  id Utf8,
  applied_at Timestamp,
  PRIMARY KEY (id)
);
