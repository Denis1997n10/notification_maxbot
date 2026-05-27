CREATE TABLE IF NOT EXISTS house_street_links (
  house_id Utf8,
  street_id Utf8,
  updated_at Timestamp,
  PRIMARY KEY (house_id),
  INDEX idx_street_id GLOBAL ON (street_id)
);
