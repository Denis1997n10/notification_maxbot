CREATE TABLE IF NOT EXISTS houses (
  house_id Utf8,
  district_id Utf8,
  title Utf8,
  is_active Bool,
  created_at Timestamp,
  PRIMARY KEY (house_id)
);
