CREATE TABLE IF NOT EXISTS feature_flags (
  code Utf8,
  enabled Bool,
  updated_at Timestamp,
  PRIMARY KEY (code)
);
