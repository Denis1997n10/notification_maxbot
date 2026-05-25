CREATE TABLE IF NOT EXISTS subscriptions (
  subscription_id Utf8,
  user_id Utf8,
  subject_id Utf8,
  event_type Utf8,
  is_active Bool,
  created_at Timestamp,
  deactivated_at Timestamp,
  PRIMARY KEY (subscription_id)
);
