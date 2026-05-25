CREATE TABLE IF NOT EXISTS entrances (
  entrance_id Utf8,
  house_id Utf8,
  title Utf8,
  public_code Utf8,
  regioncity_external_ref Utf8,
  is_active Bool,
  created_at Timestamp,
  PRIMARY KEY (entrance_id)
);
