CREATE TABLE IF NOT EXISTS admin_district_permissions (
  admin_id Utf8,
  district_id Utf8,
  PRIMARY KEY (admin_id, district_id)
);
