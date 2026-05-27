CREATE TABLE IF NOT EXISTS houses (
  id Utf8,
  district_id Utf8,
  city Utf8,
  street Utf8,
  house_number Utf8,
  building Utf8,
  is_active Bool,
  created_at Timestamp,
  updated_at Timestamp,
  PRIMARY KEY (id),
  INDEX idx_district_id GLOBAL ON (district_id)
);
