CREATE TABLE IF NOT EXISTS subscriptions (
  id Utf8,
  user_id Utf8,
  subject_type Utf8,
  subject_id Utf8,
  event_type Utf8,
  channel Utf8,
  is_active Bool,
  created_at Timestamp,
  updated_at Timestamp,
  PRIMARY KEY (id),
  INDEX idx_user_id GLOBAL ON (user_id),
  INDEX idx_subject GLOBAL ON (subject_type, subject_id),
  INDEX idx_active_unique GLOBAL ON (user_id, subject_type, subject_id, event_type, channel)
);
