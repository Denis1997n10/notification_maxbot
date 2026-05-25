CREATE TABLE IF NOT EXISTS schema_migrations (
  version Utf8,
  applied_at Timestamp,
  PRIMARY KEY (version)
);
