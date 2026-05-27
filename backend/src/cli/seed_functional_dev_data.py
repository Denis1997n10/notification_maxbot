from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from composition.container import build_container


def _hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def main() -> None:
    c = build_container()
    session = c.admin_service.session

    created, skipped = 0, 0

    # admin
    login = "admin"
    row = session.execute("SELECT id FROM admin_users VIEW idx_login WHERE login=$login LIMIT 1", {"$login": login})
    if row:
        skipped += 1
    else:
        session.execute(
            "UPSERT INTO admin_users (id, login, password_hash, role, is_active, created_at, updated_at) VALUES ($id,$login,$password_hash,$role,true,$created_at,$updated_at)",
            {"$id": str(uuid4()), "$login": login, "$password_hash": _hash_password("admin"), "$role": "super_admin", "$created_at": datetime.now(UTC), "$updated_at": datetime.now(UTC)},
        )
        created += 1

    district_id = str(uuid4())
    districts = session.execute("SELECT id FROM districts WHERE name=$name LIMIT 1", {"$name": "Тестовый район"})
    if districts:
        district_id = districts[0]["id"]
        skipped += 1
    else:
        session.execute("UPSERT INTO districts (id,name,is_active,created_at,updated_at) VALUES ($id,$name,true,$created_at,$updated_at)", {"$id": district_id, "$name": "Тестовый район", "$created_at": datetime.now(UTC), "$updated_at": datetime.now(UTC)})
        created += 1

    houses = session.execute("SELECT id FROM houses WHERE district_id=$district_id AND street=$street AND house_number=$house_number LIMIT 1", {"$district_id": district_id, "$street": "улица Доватора", "$house_number": "3"})
    if houses:
        house_id = houses[0]["id"]
        skipped += 1
    else:
        house_id = str(uuid4())
        session.execute("UPSERT INTO houses (id,district_id,city,street,house_number,building,is_active,created_at,updated_at) VALUES ($id,$district_id,$city,$street,$house_number,$building,true,$created_at,$updated_at)", {"$id": house_id, "$district_id": district_id, "$city": "Москва", "$street": "улица Доватора", "$house_number": "3", "$building": "", "$created_at": datetime.now(UTC), "$updated_at": datetime.now(UTC)})
        created += 1

    entrance = session.execute("SELECT id FROM entrances VIEW idx_public_code WHERE public_code=$public_code LIMIT 1", {"$public_code": "test"})
    if entrance:
        skipped += 1
    else:
        session.execute("UPSERT INTO entrances (id,house_id,entrance_number,public_code,regioncity_external_ref,is_active,created_at,updated_at) VALUES ($id,$house_id,$entrance_number,$public_code,$regioncity_external_ref,true,$created_at,$updated_at)", {"$id": str(uuid4()), "$house_id": house_id, "$entrance_number": "2", "$public_code": "test", "$regioncity_external_ref": "18864279", "$created_at": datetime.now(UTC), "$updated_at": datetime.now(UTC)})
        created += 1

    session.execute("UPSERT INTO feature_flags (code,enabled,updated_at) VALUES ($code,$enabled,$updated_at)", {"$code": "services_enabled", "$enabled": False, "$updated_at": datetime.now(UTC)})

    print({"created": created, "skipped": skipped})


if __name__ == "__main__":
    main()
