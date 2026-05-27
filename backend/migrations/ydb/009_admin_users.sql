CREATE TABLE IF NOT EXISTS admin_users (
  id Utf8,
  login Utf8,
  password_hash Utf8,
  role Utf8,
  is_active Bool,
  created_at Timestamp,
  updated_at Timestamp,
  PRIMARY KEY (id),
  INDEX idx_login GLOBAL ON (login)
);
