from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

from composition.container import build_container


def main() -> None:
    login = os.environ.get("ADMIN_BOOTSTRAP_LOGIN", "").strip()
    password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "")
    role = os.environ.get("ADMIN_BOOTSTRAP_ROLE", "super_admin").strip()
    if not login or len(password) < 12:
        raise SystemExit("ADMIN_BOOTSTRAP_LOGIN and ADMIN_BOOTSTRAP_PASSWORD (minimum 12 characters) are required")
    if role not in {"super_admin", "district_admin"}:
        raise SystemExit("ADMIN_BOOTSTRAP_ROLE must be super_admin or district_admin")

    container = build_container()
    service = container.admin_service
    now = datetime.now(UTC)
    existing = service.session.execute(
        "SELECT id FROM admin_users VIEW idx_login WHERE login=$login LIMIT 1",
        {"$login": login},
    )
    admin_id = existing[0]["id"] if existing else str(uuid4())
    service.session.execute(
        """
        UPSERT INTO admin_users (id, login, password_hash, role, is_active, created_at, updated_at)
        VALUES ($id, $login, $password_hash, $role, true, $created_at, $updated_at)
        """,
        {
            "$id": admin_id,
            "$login": login,
            "$password_hash": service.hash_password(password),
            "$role": role,
            "$created_at": now,
            "$updated_at": now,
        },
    )
    print({"admin_login": login, "role": role, "updated": bool(existing)})


if __name__ == "__main__":
    main()
