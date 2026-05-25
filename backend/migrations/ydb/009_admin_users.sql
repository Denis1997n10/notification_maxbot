CREATE TABLE IF NOT EXISTS admin_users (
  admin_id Utf8,
  role Utf8,
  is_active Bool,
  PRIMARY KEY (admin_id)
);
