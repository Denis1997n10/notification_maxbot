CREATE TABLE IF NOT EXISTS users (
  user_id Utf8,
  channel Utf8,
  notifications_enabled Bool,
  is_active Bool,
  created_at Timestamp,
  PRIMARY KEY (user_id)
);
