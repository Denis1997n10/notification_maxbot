CREATE TABLE IF NOT EXISTS streets (
  id Utf8,
  district_id Utf8,
  name Utf8,
  is_active Bool,
  created_at Timestamp,
  updated_at Timestamp,
  PRIMARY KEY (id),
  INDEX idx_district_id GLOBAL ON (district_id)
);
