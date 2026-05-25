CREATE TABLE IF NOT EXISTS feature_flags (
  flag_key Utf8,
  enabled Bool,
  PRIMARY KEY (flag_key)
);
