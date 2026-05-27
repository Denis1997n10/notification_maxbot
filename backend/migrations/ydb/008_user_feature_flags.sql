CREATE TABLE IF NOT EXISTS user_feature_flags (
  user_id Utf8,
  code Utf8,
  enabled Bool,
  updated_at Timestamp,
  PRIMARY KEY (user_id, code)
);
