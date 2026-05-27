CREATE TABLE IF NOT EXISTS district_city_links (
  district_id Utf8,
  city_id Utf8,
  updated_at Timestamp,
  PRIMARY KEY (district_id),
  INDEX idx_city_id GLOBAL ON (city_id)
);
