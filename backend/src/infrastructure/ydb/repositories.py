from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from domain.entities.models import AdminUser, Subject, Subscription, User
from domain.ports.interfaces import (
    AdminPermissionRepository,
    AdminUserRepository,
    FeatureFlagRepository,
    ProcessedEventRepository,
    PublicPageCacheRepository,
    SubjectRepository,
    SubscriptionRepository,
    UserFeatureFlagRepository,
    UserRepository,
)
from domain.value_objects.enums import AdminRole, SubjectType
from infrastructure.ydb.client import YdbSession


def _now() -> datetime:
    return datetime.now(UTC)


class YdbUserRepository(UserRepository):
    def __init__(self, session: YdbSession) -> None:
        self.session = session

    def get_by_id(self, user_id: str) -> User | None:
        rows = self.session.execute("SELECT * FROM users WHERE id=$id LIMIT 1", {"$id": user_id})
        if not rows:
            return None
        r = rows[0]
        return User(user_id=r["id"], channel=r["channel"], is_active=r["is_active"])

    def save(self, user: User) -> None:
        self.session.execute(
            """
            UPSERT INTO users (id, channel, external_user_id, display_name, is_active, created_at, updated_at)
            VALUES ($id, $channel, $external_user_id, $display_name, $is_active, $created_at, $updated_at)
            """,
            {
                "$id": user.user_id,
                "$channel": str(user.channel),
                "$external_user_id": user.user_id,
                "$display_name": "",
                "$is_active": user.is_active,
                "$created_at": _now(),
                "$updated_at": _now(),
            },
        )

    def find_by_channel_user(self, channel: str, external_user_id: str) -> User | None:
        rows = self.session.execute(
            "SELECT * FROM users VIEW idx_channel_external WHERE channel=$channel AND external_user_id=$external_user_id LIMIT 1",
            {"$channel": channel, "$external_user_id": external_user_id},
        )
        if not rows:
            return None
        r = rows[0]
        return User(user_id=r["id"], channel=r["channel"], is_active=r["is_active"])

    def get_or_create_channel_user(self, channel: str, external_user_id: str, display_name: str = "") -> User:
        existing = self.find_by_channel_user(channel, external_user_id)
        if existing:
            return existing
        user = User(user_id=str(uuid4()), channel=channel)
        self.session.execute(
            """
            UPSERT INTO users (id, channel, external_user_id, display_name, is_active, created_at, updated_at)
            VALUES ($id, $channel, $external_user_id, $display_name, true, $created_at, $updated_at)
            """,
            {
                "$id": user.user_id,
                "$channel": channel,
                "$external_user_id": external_user_id,
                "$display_name": display_name,
                "$created_at": _now(),
                "$updated_at": _now(),
            },
        )
        return user

    def list_active_for_admin(self) -> list[dict]:
        return self.session.execute(
            "SELECT id, channel, external_user_id, display_name, is_active, created_at, updated_at "
            "FROM users WHERE is_active=true"
        )

    def deactivate_for_admin(self, user_id: str) -> dict | None:
        rows = self.session.execute("SELECT * FROM users WHERE id=$id LIMIT 1", {"$id": user_id})
        if not rows:
            return None
        row = rows[0]
        row["is_active"] = False
        row["updated_at"] = _now()
        self.session.execute(
            """
            UPSERT INTO users (id,channel,external_user_id,display_name,is_active,created_at,updated_at)
            VALUES ($id,$channel,$external_user_id,$display_name,false,$created_at,$updated_at)
            """,
            {
                "$id": row["id"],
                "$channel": row["channel"],
                "$external_user_id": row["external_user_id"],
                "$display_name": row.get("display_name", ""),
                "$created_at": row["created_at"],
                "$updated_at": row["updated_at"],
            },
        )
        return row


class YdbSubjectRepository(SubjectRepository):
    def __init__(self, session: YdbSession) -> None:
        self.session = session

    def get_entrance_page_data(self, public_code: str) -> dict | None:
        rows = self.session.execute(
            """
            SELECT e.public_code AS public_code,
                   e.entrance_number AS entrance_number,
                   e.is_active AS is_active,
                   d.name AS district_name,
                   h.city AS city,
                   h.street AS street,
                   h.house_number AS house_number,
                   h.building AS building
            FROM entrances AS e
            INNER JOIN houses AS h ON h.id = e.house_id
            INNER JOIN districts AS d ON d.id = h.district_id
            WHERE e.public_code=$code
              AND e.is_active=true
              AND h.is_active=true
              AND d.is_active=true
            LIMIT 1
            """,
            {"$code": public_code},
        )
        if not rows:
            return None
        row = rows[0]
        building = f" к{row['building']}" if row.get("building") else ""
        row["house_name"] = f"{row['city']}, {row['street']} {row['house_number']}{building}"
        row["address"] = f"{row['house_name']}, подъезд {row['entrance_number']}"
        return row

    def _map_entrance(self, row: dict) -> Subject:
        building = f" к{row['building']}" if row.get("building") else ""
        if row.get("city") and row.get("street") and row.get("house_number"):
            title = f"{row['city']}, {row['street']} {row['house_number']}{building}, подъезд {row.get('entrance_number', '')}"
        else:
            title = f"Подъезд {row.get('entrance_number', '')}".strip()
        return Subject(subject_id=row["id"], subject_type=SubjectType.ENTRANCE, title=title, is_active=row.get("is_active", True), external_ref=row.get("regioncity_external_ref"))

    def get_by_id(self, subject_id: str) -> Subject | None:
        rows = self.session.execute(
            """
            SELECT e.id AS id,
                   e.entrance_number AS entrance_number,
                   e.regioncity_external_ref AS regioncity_external_ref,
                   e.is_active AS is_active,
                   h.city AS city,
                   h.street AS street,
                   h.house_number AS house_number,
                   h.building AS building
            FROM entrances AS e
            INNER JOIN houses AS h ON h.id = e.house_id
            INNER JOIN districts AS d ON d.id = h.district_id
            WHERE e.id=$id
              AND e.is_active=true
              AND h.is_active=true
              AND d.is_active=true
            LIMIT 1
            """,
            {"$id": subject_id},
        )
        return self._map_entrance(rows[0]) if rows else None

    def get_by_public_code(self, public_code: str) -> Subject | None:
        rows = self.session.execute("SELECT id FROM entrances VIEW idx_public_code WHERE public_code=$code AND is_active=true LIMIT 1", {"$code": public_code})
        return self.get_by_id(rows[0]["id"]) if rows else None

    def find_by_external_ref(self, external_ref: str) -> Subject | None:
        rows = self.session.execute("SELECT id FROM entrances VIEW idx_regioncity_external_ref WHERE regioncity_external_ref=$ref AND is_active=true LIMIT 1", {"$ref": external_ref})
        return self.get_by_id(rows[0]["id"]) if rows else None

    def list_active(self) -> list[Subject]:
        rows = self.session.execute("SELECT * FROM entrances WHERE is_active=true")
        return [self._map_entrance(r) for r in rows]

    def list_districts(self, active_only: bool = True) -> list[dict]:
        where = "WHERE is_active=true" if active_only else ""
        return self.session.execute(f"SELECT * FROM districts {where}")

    def list_cities(self, active_only: bool = True) -> list[dict]:
        where = "WHERE is_active=true" if active_only else ""
        return self.session.execute(f"SELECT * FROM cities {where}")

    def get_city(self, city_id: str) -> dict | None:
        rows = self.session.execute("SELECT * FROM cities WHERE id=$id LIMIT 1", {"$id": city_id})
        return rows[0] if rows else None

    def create_city(self, name: str) -> dict:
        row = {"id": str(uuid4()), "name": name, "is_active": True, "created_at": _now(), "updated_at": _now()}
        self.session.execute(
            "UPSERT INTO cities (id,name,is_active,created_at,updated_at) VALUES ($id,$name,true,$created_at,$updated_at)",
            {"$id": row["id"], "$name": row["name"], "$created_at": row["created_at"], "$updated_at": row["updated_at"]},
        )
        return row

    def link_district_to_city(self, city_id: str, district_id: str) -> None:
        self.session.execute(
            "UPSERT INTO district_city_links (district_id,city_id,updated_at) VALUES ($district_id,$city_id,$updated_at)",
            {"$district_id": district_id, "$city_id": city_id, "$updated_at": _now()},
        )

    def list_districts_by_city(self, city_id: str, active_only: bool = True) -> list[dict]:
        links = self.session.execute(
            "SELECT district_id FROM district_city_links VIEW idx_city_id WHERE city_id=$city_id",
            {"$city_id": city_id},
        )
        items: list[dict] = []
        for link in links:
            item = self.get_district(link["district_id"])
            if item and (not active_only or item.get("is_active", True)):
                items.append(item)
        return items

    def list_unassigned_districts(self) -> list[dict]:
        linked_ids = {row["district_id"] for row in self.session.execute("SELECT district_id FROM district_city_links")}
        return [item for item in self.list_districts() if item["id"] not in linked_ids]

    def get_city_for_district(self, district_id: str) -> dict | None:
        links = self.session.execute(
            "SELECT city_id FROM district_city_links WHERE district_id=$district_id LIMIT 1",
            {"$district_id": district_id},
        )
        return self.get_city(links[0]["city_id"]) if links else None

    def list_houses_by_district(self, district_id: str, active_only: bool = True) -> list[dict]:
        where = "AND is_active=true" if active_only else ""
        return self.session.execute(f"SELECT * FROM houses VIEW idx_district_id WHERE district_id=$district_id {where}", {"$district_id": district_id})

    def list_entrances_by_house(self, house_id: str, active_only: bool = True) -> list[dict]:
        where = "AND is_active=true" if active_only else ""
        return self.session.execute(f"SELECT * FROM entrances VIEW idx_house_id WHERE house_id=$house_id {where}", {"$house_id": house_id})

    def get_district(self, district_id: str) -> dict | None:
        rows = self.session.execute("SELECT * FROM districts WHERE id=$id LIMIT 1", {"$id": district_id})
        return rows[0] if rows else None

    def get_house(self, house_id: str) -> dict | None:
        rows = self.session.execute("SELECT * FROM houses WHERE id=$id LIMIT 1", {"$id": house_id})
        return rows[0] if rows else None

    def get_entrance(self, entrance_id: str) -> dict | None:
        rows = self.session.execute("SELECT * FROM entrances WHERE id=$id LIMIT 1", {"$id": entrance_id})
        return rows[0] if rows else None

    def create_district(self, name: str, city_id: str | None = None) -> dict:
        row = {"id": str(uuid4()), "name": name, "is_active": True, "created_at": _now(), "updated_at": _now()}
        self.session.execute(
            "UPSERT INTO districts (id,name,is_active,created_at,updated_at) VALUES ($id,$name,true,$created_at,$updated_at)",
            {"$id": row["id"], "$name": row["name"], "$created_at": row["created_at"], "$updated_at": row["updated_at"]},
        )
        if city_id:
            self.link_district_to_city(city_id, row["id"])
        return row

    def list_streets_by_district(self, district_id: str, active_only: bool = True) -> list[dict]:
        where = "AND is_active=true" if active_only else ""
        return self.session.execute(
            f"SELECT * FROM streets VIEW idx_district_id WHERE district_id=$district_id {where}",
            {"$district_id": district_id},
        )

    def get_street(self, street_id: str) -> dict | None:
        rows = self.session.execute("SELECT * FROM streets WHERE id=$id LIMIT 1", {"$id": street_id})
        return rows[0] if rows else None

    def create_street(self, district_id: str, name: str) -> dict:
        row = {
            "id": str(uuid4()),
            "district_id": district_id,
            "name": name,
            "is_active": True,
            "created_at": _now(),
            "updated_at": _now(),
        }
        self.session.execute(
            "UPSERT INTO streets (id,district_id,name,is_active,created_at,updated_at) "
            "VALUES ($id,$district_id,$name,true,$created_at,$updated_at)",
            {
                "$id": row["id"],
                "$district_id": row["district_id"],
                "$name": row["name"],
                "$created_at": row["created_at"],
                "$updated_at": row["updated_at"],
            },
        )
        return row

    def link_house_to_street(self, street_id: str, house_id: str) -> None:
        self.session.execute(
            "UPSERT INTO house_street_links (house_id,street_id,updated_at) VALUES ($house_id,$street_id,$updated_at)",
            {"$house_id": house_id, "$street_id": street_id, "$updated_at": _now()},
        )

    def list_houses_by_street(self, street_id: str, active_only: bool = True) -> list[dict]:
        links = self.session.execute(
            "SELECT house_id FROM house_street_links VIEW idx_street_id WHERE street_id=$street_id",
            {"$street_id": street_id},
        )
        items: list[dict] = []
        for link in links:
            item = self.get_house(link["house_id"])
            if item and (not active_only or item.get("is_active", True)):
                items.append(item)
        return items

    def create_house(self, district_id: str, city: str, street: str, house_number: str, building: str, street_id: str | None = None) -> dict:
        row = {
            "id": str(uuid4()),
            "district_id": district_id,
            "city": city,
            "street": street,
            "house_number": house_number,
            "building": building,
            "is_active": True,
            "created_at": _now(),
            "updated_at": _now(),
        }
        self.session.execute(
            """
            UPSERT INTO houses (id,district_id,city,street,house_number,building,is_active,created_at,updated_at)
            VALUES ($id,$district_id,$city,$street,$house_number,$building,true,$created_at,$updated_at)
            """,
            {
                "$id": row["id"],
                "$district_id": row["district_id"],
                "$city": row["city"],
                "$street": row["street"],
                "$house_number": row["house_number"],
                "$building": row["building"],
                "$created_at": row["created_at"],
                "$updated_at": row["updated_at"],
            },
        )
        if street_id:
            self.link_house_to_street(street_id, row["id"])
        return row

    def create_entrance(self, house_id: str, entrance_number: str, public_code: str, external_ref: str) -> dict | None:
        existing = self.session.execute(
            "SELECT id FROM entrances VIEW idx_public_code WHERE public_code=$public_code LIMIT 1",
            {"$public_code": public_code},
        )
        if existing:
            return None
        row = {
            "id": str(uuid4()),
            "house_id": house_id,
            "entrance_number": entrance_number,
            "public_code": public_code,
            "regioncity_external_ref": external_ref,
            "is_active": True,
            "created_at": _now(),
            "updated_at": _now(),
        }
        self.session.execute(
            """
            UPSERT INTO entrances (id,house_id,entrance_number,public_code,regioncity_external_ref,is_active,created_at,updated_at)
            VALUES ($id,$house_id,$entrance_number,$public_code,$regioncity_external_ref,true,$created_at,$updated_at)
            """,
            {
                "$id": row["id"],
                "$house_id": row["house_id"],
                "$entrance_number": row["entrance_number"],
                "$public_code": row["public_code"],
                "$regioncity_external_ref": row["regioncity_external_ref"],
                "$created_at": row["created_at"],
                "$updated_at": row["updated_at"],
            },
        )
        return row

    def deactivate_district(self, district_id: str) -> dict | None:
        row = self.get_district(district_id)
        if not row:
            return None
        for house in self.list_houses_by_district(district_id, active_only=False):
            self.deactivate_house(house["id"])
        row["is_active"] = False
        row["updated_at"] = _now()
        self.session.execute(
            "UPSERT INTO districts (id,name,is_active,created_at,updated_at) VALUES ($id,$name,false,$created_at,$updated_at)",
            {"$id": row["id"], "$name": row["name"], "$created_at": row["created_at"], "$updated_at": row["updated_at"]},
        )
        return row

    def deactivate_city(self, city_id: str) -> dict | None:
        row = self.get_city(city_id)
        if not row:
            return None
        for district in self.list_districts_by_city(city_id, active_only=False):
            self.deactivate_district(district["id"])
        row["is_active"] = False
        row["updated_at"] = _now()
        self.session.execute(
            "UPSERT INTO cities (id,name,is_active,created_at,updated_at) VALUES ($id,$name,false,$created_at,$updated_at)",
            {"$id": row["id"], "$name": row["name"], "$created_at": row["created_at"], "$updated_at": row["updated_at"]},
        )
        return row

    def deactivate_street(self, street_id: str) -> dict | None:
        row = self.get_street(street_id)
        if not row:
            return None
        for house in self.list_houses_by_street(street_id, active_only=False):
            self.deactivate_house(house["id"])
        row["is_active"] = False
        row["updated_at"] = _now()
        self.session.execute(
            "UPSERT INTO streets (id,district_id,name,is_active,created_at,updated_at) "
            "VALUES ($id,$district_id,$name,false,$created_at,$updated_at)",
            {
                "$id": row["id"],
                "$district_id": row["district_id"],
                "$name": row["name"],
                "$created_at": row["created_at"],
                "$updated_at": row["updated_at"],
            },
        )
        return row

    def deactivate_house(self, house_id: str) -> dict | None:
        row = self.get_house(house_id)
        if not row:
            return None
        for entrance in self.list_entrances_by_house(house_id, active_only=False):
            self.deactivate_entrance(entrance["id"])
        row["is_active"] = False
        row["updated_at"] = _now()
        self.session.execute(
            """
            UPSERT INTO houses (id,district_id,city,street,house_number,building,is_active,created_at,updated_at)
            VALUES ($id,$district_id,$city,$street,$house_number,$building,false,$created_at,$updated_at)
            """,
            {
                "$id": row["id"],
                "$district_id": row["district_id"],
                "$city": row["city"],
                "$street": row["street"],
                "$house_number": row["house_number"],
                "$building": row["building"],
                "$created_at": row["created_at"],
                "$updated_at": row["updated_at"],
            },
        )
        return row

    def deactivate_entrance(self, entrance_id: str) -> dict | None:
        row = self.get_entrance(entrance_id)
        if not row:
            return None
        row["is_active"] = False
        row["updated_at"] = _now()
        self.session.execute(
            """
            UPSERT INTO entrances (id,house_id,entrance_number,public_code,regioncity_external_ref,is_active,created_at,updated_at)
            VALUES ($id,$house_id,$entrance_number,$public_code,$regioncity_external_ref,false,$created_at,$updated_at)
            """,
            {
                "$id": row["id"],
                "$house_id": row["house_id"],
                "$entrance_number": row["entrance_number"],
                "$public_code": row["public_code"],
                "$regioncity_external_ref": row.get("regioncity_external_ref", ""),
                "$created_at": row["created_at"],
                "$updated_at": row["updated_at"],
            },
        )
        return row


class YdbSubscriptionRepository(SubscriptionRepository):
    def __init__(self, session: YdbSession) -> None:
        self.session = session

    def list_active_by_user(self, user_id: str) -> list[Subscription]:
        rows = self.session.execute("SELECT * FROM subscriptions VIEW idx_user_id WHERE user_id=$user_id AND is_active=true", {"$user_id": user_id})
        return [Subscription(subscription_id=r["id"], user_id=r["user_id"], subject_id=r["subject_id"], is_active=r["is_active"], created_at=r["created_at"]) for r in rows]

    def get_active(self, user_id: str, subject_id: str) -> Subscription | None:
        rows = self.session.execute(
            "SELECT * FROM subscriptions VIEW idx_user_id WHERE user_id=$user_id AND subject_id=$subject_id AND is_active=true LIMIT 1",
            {"$user_id": user_id, "$subject_id": subject_id},
        )
        if not rows:
            return None
        r = rows[0]
        return Subscription(subscription_id=r["id"], user_id=r["user_id"], subject_id=r["subject_id"], is_active=r["is_active"], created_at=r["created_at"])

    def save(self, subscription: Subscription) -> None:
        self.session.execute(
            """
            UPSERT INTO subscriptions (id,user_id,subject_type,subject_id,event_type,channel,is_active,created_at,updated_at)
            VALUES ($id,$user_id,$subject_type,$subject_id,$event_type,$channel,true,$created_at,$updated_at)
            """,
            {
                "$id": subscription.subscription_id,
                "$user_id": subscription.user_id,
                "$subject_type": "entrance",
                "$subject_id": subscription.subject_id,
                "$event_type": "cleaning.completed",
                "$channel": "max",
                "$created_at": subscription.created_at,
                "$updated_at": _now(),
            },
        )

    def deactivate(self, user_id: str, subject_id: str) -> None:
        rows = self.session.execute(
            "SELECT * FROM subscriptions VIEW idx_user_id WHERE user_id=$user_id AND subject_id=$subject_id AND is_active=true",
            {"$user_id": user_id, "$subject_id": subject_id},
        )
        for r in rows:
            self.session.execute("UPSERT INTO subscriptions (id,user_id,subject_type,subject_id,event_type,channel,is_active,created_at,updated_at) VALUES ($id,$user_id,$subject_type,$subject_id,$event_type,$channel,false,$created_at,$updated_at)", {"$id": r["id"], "$user_id": r["user_id"], "$subject_type": r["subject_type"], "$subject_id": r["subject_id"], "$event_type": r["event_type"], "$channel": r["channel"], "$created_at": r["created_at"], "$updated_at": _now()})

    def deactivate_all(self, user_id: str) -> int:
        rows = self.session.execute("SELECT * FROM subscriptions VIEW idx_user_id WHERE user_id=$user_id AND is_active=true", {"$user_id": user_id})
        for r in rows:
            self.deactivate(user_id, r["subject_id"])
        return len(rows)


class YdbProcessedEventRepository(ProcessedEventRepository):
    def __init__(self, session: YdbSession) -> None:
        self.session = session

    def is_processed(self, source: str, external_id: str, event_type: str) -> bool:
        rows = self.session.execute("SELECT external_id FROM processed_events WHERE source=$source AND external_id=$external_id AND event_type=$event_type LIMIT 1", {"$source": source, "$external_id": external_id, "$event_type": event_type})
        return bool(rows)

    def mark_processed(self, source: str, external_id: str, event_type: str, processed_at: datetime) -> None:
        self.session.execute("UPSERT INTO processed_events (source, external_id, event_type, subject_type, subject_id, processed_at) VALUES ($source,$external_id,$event_type,$subject_type,$subject_id,$processed_at)", {"$source": source, "$external_id": external_id, "$event_type": event_type, "$subject_type": "entrance", "$subject_id": "", "$processed_at": processed_at})


class YdbFeatureFlagRepository(FeatureFlagRepository):
    def __init__(self, session: YdbSession) -> None:
        self.session = session

    def is_enabled(self, key: str) -> bool:
        rows = self.session.execute("SELECT enabled FROM feature_flags WHERE code=$key LIMIT 1", {"$key": key})
        return bool(rows and rows[0]["enabled"])


class YdbUserFeatureFlagRepository(UserFeatureFlagRepository):
    def __init__(self, session: YdbSession) -> None:
        self.session = session

    def is_enabled_for_user(self, user_id: str, key: str) -> bool:
        rows = self.session.execute("SELECT enabled FROM user_feature_flags WHERE user_id=$user_id AND code=$key LIMIT 1", {"$user_id": user_id, "$key": key})
        return bool(rows[0]["enabled"]) if rows else False


class YdbAdminUserRepository(AdminUserRepository):
    def __init__(self, session: YdbSession) -> None:
        self.session = session

    def get_by_id(self, admin_id: str) -> AdminUser | None:
        rows = self.session.execute("SELECT * FROM admin_users WHERE id=$id LIMIT 1", {"$id": admin_id})
        if not rows:
            return None
        r = rows[0]
        return AdminUser(admin_id=r["id"], role=AdminRole(r["role"]))

    def find_by_login(self, login: str) -> dict | None:
        rows = self.session.execute("SELECT * FROM admin_users VIEW idx_login WHERE login=$login AND is_active=true LIMIT 1", {"$login": login})
        return rows[0] if rows else None

    def find_any_by_login(self, login: str) -> dict | None:
        rows = self.session.execute("SELECT * FROM admin_users VIEW idx_login WHERE login=$login LIMIT 1", {"$login": login})
        return rows[0] if rows else None

    def list_active_for_admin(self) -> list[dict]:
        return self.session.execute("SELECT id, login, role, is_active, created_at, updated_at FROM admin_users WHERE is_active=true")

    def create_for_admin(self, login: str, password_hash: str, role: str) -> dict:
        row = {
            "id": str(uuid4()),
            "login": login,
            "role": role,
            "is_active": True,
            "created_at": _now(),
            "updated_at": _now(),
        }
        self.session.execute(
            """
            UPSERT INTO admin_users (id,login,password_hash,role,is_active,created_at,updated_at)
            VALUES ($id,$login,$password_hash,$role,true,$created_at,$updated_at)
            """,
            {
                "$id": row["id"],
                "$login": row["login"],
                "$password_hash": password_hash,
                "$role": row["role"],
                "$created_at": row["created_at"],
                "$updated_at": row["updated_at"],
            },
        )
        return row

    def deactivate_for_admin(self, admin_id: str) -> dict | None:
        rows = self.session.execute("SELECT * FROM admin_users WHERE id=$id LIMIT 1", {"$id": admin_id})
        if not rows:
            return None
        row = rows[0]
        row["is_active"] = False
        row["updated_at"] = _now()
        self.session.execute(
            """
            UPSERT INTO admin_users (id,login,password_hash,role,is_active,created_at,updated_at)
            VALUES ($id,$login,$password_hash,$role,false,$created_at,$updated_at)
            """,
            {
                "$id": row["id"],
                "$login": row["login"],
                "$password_hash": row["password_hash"],
                "$role": row["role"],
                "$created_at": row["created_at"],
                "$updated_at": row["updated_at"],
            },
        )
        return {key: value for key, value in row.items() if key != "password_hash"}


class YdbAdminPermissionRepository(AdminPermissionRepository):
    def __init__(self, session: YdbSession) -> None:
        self.session = session

    def can_manage_subject(self, admin_id: str, district_id: str) -> bool:
        rows = self.session.execute("SELECT district_id FROM admin_district_permissions WHERE admin_user_id=$admin_user_id AND district_id=$district_id LIMIT 1", {"$admin_user_id": admin_id, "$district_id": district_id})
        return bool(rows)

    def list_district_ids(self, admin_id: str) -> list[str]:
        rows = self.session.execute(
            "SELECT district_id FROM admin_district_permissions WHERE admin_user_id=$admin_user_id",
            {"$admin_user_id": admin_id},
        )
        return [row["district_id"] for row in rows]

    def grant_districts(self, admin_id: str, district_ids: list[str]) -> None:
        for district_id in district_ids:
            self.session.execute(
                "UPSERT INTO admin_district_permissions (admin_user_id,district_id) VALUES ($admin_user_id,$district_id)",
                {"$admin_user_id": admin_id, "$district_id": district_id},
            )


class YdbPublicPageCacheRepository(PublicPageCacheRepository):
    def __init__(self, session: YdbSession) -> None:
        self.session = session

    def get(self, key: str):
        rows = self.session.execute("SELECT payload_json, expires_at FROM public_page_cache WHERE cache_key=$key LIMIT 1", {"$key": key})
        if not rows:
            return None
        row = rows[0]
        if row["expires_at"] < _now():
            return None
        return json.loads(row["payload_json"])

    def set(self, key: str, value: dict, ttl_seconds: int) -> None:
        expires_at = _now() + timedelta(seconds=ttl_seconds)
        self.session.execute("UPSERT INTO public_page_cache (cache_key, payload_json, expires_at) VALUES ($k,$p,$e)", {"$k": key, "$p": json.dumps(value, ensure_ascii=False), "$e": expires_at})
