CREATE TABLE IF NOT EXISTS users (
  id Utf8,
  channel Utf8,
  external_user_id Utf8,
  display_name Utf8,
  is_active Bool,
  created_at Timestamp,
  updated_at Timestamp,
  PRIMARY KEY (id),
  INDEX idx_channel_external GLOBAL ON (channel, external_user_id)
);
