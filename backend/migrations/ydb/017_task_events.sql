CREATE TABLE IF NOT EXISTS task_events (
  source Utf8,
  external_id Utf8,
  event_type Utf8,
  subject_id Utf8,
  occurred_at Timestamp,
  metadata_json Utf8,
  created_at Timestamp,
  PRIMARY KEY (source, external_id, event_type),
  INDEX idx_subject_id GLOBAL ON (subject_id)
);
