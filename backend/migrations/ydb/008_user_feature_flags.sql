CREATE TABLE IF NOT EXISTS user_feature_flags (
  user_id Utf8,
  flag_key Utf8,
  enabled Bool,
  PRIMARY KEY (user_id, flag_key)
);
