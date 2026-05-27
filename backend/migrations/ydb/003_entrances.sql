CREATE TABLE IF NOT EXISTS entrances (
  id Utf8,
  house_id Utf8,
  entrance_number Utf8,
  public_code Utf8,
  regioncity_external_ref Utf8,
  is_active Bool,
  created_at Timestamp,
  updated_at Timestamp,
  PRIMARY KEY (id),
  INDEX idx_public_code GLOBAL ON (public_code),
  INDEX idx_regioncity_external_ref GLOBAL ON (regioncity_external_ref),
  INDEX idx_house_id GLOBAL ON (house_id)
);
