CREATE TABLE IF NOT EXISTS processed_events (
  source Utf8,
  external_id Utf8,
  event_type Utf8,
  subject_type Utf8,
  subject_id Utf8,
  processed_at Timestamp,
  PRIMARY KEY (source, external_id, event_type)
);
