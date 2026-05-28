from __future__ import annotations

from dataclasses import dataclass
import asyncio
import base64
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
import hashlib
import hmac
import json
import os
import secrets
from typing import Any
from uuid import uuid4

from application.services import NotificationService
from application.templates.code_template_provider import CodeTemplateProvider
from application.use_cases.use_cases import (
    DisableAllUserNotificationsUseCase,
    ListUserSubscriptionsUseCase,
    SubscribeUserToSubjectUseCase,
)
from config.settings import load_settings
from domain.entities.models import Subscription, TaskEvent
from domain.ports.interfaces import SecretProvider
from domain.value_objects.enums import EventType, Source
from infrastructure.lockbox.secret_provider import YandexLockboxSecretProvider
from infrastructure.max.max_client import MaxClient
from infrastructure.max.max_notification_channel import MaxNotificationChannel
from infrastructure.max.max_webapp_validator import MaxWebAppValidator
from infrastructure.max.max_webhook_parser import MaxWebhookParser
from infrastructure.regioncity.regioncity_client import RegionCityClient
from infrastructure.ydb.client import YdbClient, YdbConfig
from infrastructure.ydb.repositories import (
    YdbAdminPermissionRepository,
    YdbAdminUserRepository,
    YdbFeatureFlagRepository,
    YdbProcessedEventRepository,
    YdbSubjectRepository,
    YdbSubscriptionRepository,
    YdbUserRepository,
)


class _Registry:
    def __init__(self, channel: MaxNotificationChannel):
        self.channel = channel

    def get(self, _: str):
        return self.channel


@dataclass
class AppContainer:
    bot_service: Any
    public_service: Any
    admin_service: Any
    polling_use_case: Any
    notification_service: Any
    bot_reply_channel: Any | None = None


class PublicService:
    def __init__(
        self,
        subjects: YdbSubjectRepository,
        users: YdbUserRepository | None = None,
        subscriptions: YdbSubscriptionRepository | None = None,
        subscribe_uc: SubscribeUserToSubjectUseCase | None = None,
        secret_provider: SecretProvider | None = None,
        max_bot_deeplink_base: str = "",
    ):
        self.subjects = subjects
        self.users = users
        self.subscriptions = subscriptions
        self.subscribe_uc = subscribe_uc
        self.secret_provider = secret_provider
        self.max_bot_deeplink_base = max_bot_deeplink_base.rstrip("/")

    def list_cities(self):
        return self.subjects.list_cities()

    def list_city_districts(self, city_id: str):
        city = self.subjects.get_city(city_id)
        if not city or not city.get("is_active", True):
            return []
        return self.subjects.list_districts_by_city(city_id)

    def list_districts(self):
        return self.subjects.list_districts()

    def list_streets(self, district_id: str):
        district = self.subjects.get_district(district_id)
        if not district or not district.get("is_active", True):
            return []
        return self.subjects.list_streets_by_district(district_id)

    def list_houses(self, district_id: str):
        return self.subjects.list_houses_by_district(district_id)

    def list_street_houses(self, street_id: str):
        street = self.subjects.get_street(street_id)
        if not street or not street.get("is_active", True):
            return []
        return self.subjects.list_houses_by_street(street_id)

    def list_entrances(self, house_id: str):
        return [self._entrance_response(item) for item in self.subjects.list_entrances_by_house(house_id)]

    def subscribe_from_mini_app(self, body: str | dict | None) -> dict:
        if not self.users or not self.subscriptions or not self.subscribe_uc or not self.secret_provider:
            return {"error": "configuration_error"}
        data = _parse_json(body)
        public_code = str(data.get("public_code") or "").strip()
        init_data = str(data.get("init_data") or "").strip()
        if not public_code or not init_data:
            return {"error": "required_fields", "fields": ["public_code", "init_data"]}
        try:
            user_data = MaxWebAppValidator(self.secret_provider.get_secret("MAX_BOT_TOKEN")).verify_user(init_data)
        except Exception:
            return {"error": "configuration_error"}
        if not user_data:
            return {"error": "unauthorized"}
        subject = self.subjects.get_by_public_code(public_code)
        if not subject:
            return {"error": "not_found"}
        user = self.users.get_or_create_channel_user("max", user_data.external_user_id, user_data.display_name)
        if self.subscriptions.get_active(user.user_id, subject.subject_id):
            return {"status": "already_subscribed", "subject": {"id": subject.subject_id, "title": subject.title}}
        self.subscribe_uc.execute(Subscription(subscription_id=str(uuid4()), user_id=user.user_id, subject_id=subject.subject_id))
        return {"status": "subscribed", "subject": {"id": subject.subject_id, "title": subject.title}}

    def get_entrance_page(self, public_code: str):
        data = self.subjects.get_entrance_page_data(public_code)
        if not data:
            return {"error": "not_found", "mock": False}
        return {
            "public_code": public_code,
            "district": data.get("district_name", ""),
            "house": data.get("house_name", ""),
            "entrance": data.get("entrance_number", ""),
            "address": data.get("address", ""),
            "public_url": self._public_url(public_code),
            "max_bot_url": self._max_bot_url(public_code),
            "events": [],
            "mock": False,
        }

    def _public_url(self, public_code: str) -> str:
        base = os.getenv("PUBLIC_SITE_URL", "").rstrip("/")
        return f"{base}/e/{public_code}" if base else f"/e/{public_code}"

    def _max_bot_url(self, public_code: str) -> str:
        return f"{self.max_bot_deeplink_base}?start=e_{public_code}" if self.max_bot_deeplink_base and public_code else ""

    def _entrance_response(self, item: dict) -> dict:
        result = dict(item)
        if item.get("public_code"):
            result["public_url"] = self._public_url(item["public_code"])
            result["max_bot_url"] = self._max_bot_url(item["public_code"])
        return result


class AdminService:
    _PASSWORD_ITERATIONS = 600_000

    def __init__(
        self,
        admin_repo: YdbAdminUserRepository,
        permissions: YdbAdminPermissionRepository,
        subjects: YdbSubjectRepository,
        users: YdbUserRepository,
        subscriptions: YdbSubscriptionRepository,
        secret_provider: SecretProvider,
        notifier: NotificationService,
        session: Any,
        public_site_url: str = "",
        max_bot_deeplink_base: str = "",
        regioncity_client: RegionCityClient | None = None,
        regioncity_map_objects_path: str = "/mapObjectManagement/mapObjects",
    ):
        self.admin_repo = admin_repo
        self.permissions = permissions
        self.subjects = subjects
        self.users = users
        self.subscriptions = subscriptions
        self.secret_provider = secret_provider
        self.notifier = notifier
        self.session = session
        self.public_site_url = public_site_url.rstrip("/")
        self.max_bot_deeplink_base = max_bot_deeplink_base.rstrip("/")
        self.regioncity_client = regioncity_client
        self.regioncity_map_objects_path = regioncity_map_objects_path

    def hash_password(self, raw: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", raw.encode(), salt, self._PASSWORD_ITERATIONS)
        return "pbkdf2_sha256${}${}${}".format(
            self._PASSWORD_ITERATIONS,
            base64.urlsafe_b64encode(salt).decode(),
            base64.urlsafe_b64encode(digest).decode(),
        )

    def _verify_password(self, raw: str, stored: str) -> bool:
        if stored.startswith("pbkdf2_sha256$"):
            _, iterations, encoded_salt, encoded_digest = stored.split("$", 3)
            salt = base64.urlsafe_b64decode(encoded_salt.encode())
            expected = base64.urlsafe_b64decode(encoded_digest.encode())
            candidate = hashlib.pbkdf2_hmac("sha256", raw.encode(), salt, int(iterations))
            return hmac.compare_digest(candidate, expected)
        return hmac.compare_digest(stored, hashlib.sha256(raw.encode()).hexdigest())

    def _jwt_secret(self) -> bytes:
        return self.secret_provider.get_secret("ADMIN_JWT_SECRET").encode()

    def _issue(self, admin_id: str, role: str) -> str:
        expires_at = int((datetime.now(UTC) + timedelta(hours=12)).timestamp())
        payload = json.dumps({"sub": admin_id, "role": role, "exp": expires_at}, ensure_ascii=False)
        sig = hmac.new(self._jwt_secret(), payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{sig}"

    def _verify(self, token: str) -> dict:
        payload, sig = token.rsplit(".", 1)
        expected = hmac.new(self._jwt_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("invalid token")
        data = json.loads(payload)
        if int(data.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
            raise ValueError("expired token")
        return data

    def login(self, body: str | dict | None):
        d = _parse_json(body)
        u = self.admin_repo.find_by_login(d.get("login", ""))
        if not u or not self._verify_password(d.get("password", ""), u["password_hash"]):
            return {"error": "invalid_credentials"}
        return {"token": self._issue(u["id"], u["role"]), "role": u["role"]}

    def me(self, headers: dict):
        auth = headers.get("Authorization") or headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return {"error": "unauthorized"}
        try:
            return self._verify(auth.replace("Bearer ", ""))
        except Exception:
            return {"error": "unauthorized"}

    def _principal(self, headers: dict) -> dict | None:
        principal = self.me(headers)
        return None if "error" in principal else principal

    def _can_manage_district(self, principal: dict, district_id: str) -> bool:
        if principal.get("role") == "super_admin":
            return True
        return self.permissions.can_manage_subject(str(principal.get("sub", "")), district_id)

    def _authorized_district(self, headers: dict, district_id: str) -> tuple[dict | None, dict | None]:
        principal = self._principal(headers)
        if not principal:
            return None, {"error": "unauthorized"}
        district = self.subjects.get_district(district_id)
        if not district or not district.get("is_active", True):
            return None, {"error": "not_found"}
        if not self._can_manage_district(principal, district_id):
            return None, {"error": "forbidden"}
        return principal, None

    def _super_admin(self, headers: dict) -> tuple[dict | None, dict | None]:
        principal = self._principal(headers)
        if not principal:
            return None, {"error": "unauthorized"}
        if principal.get("role") != "super_admin":
            return None, {"error": "forbidden"}
        return principal, None

    @staticmethod
    def _required(data: dict, names: tuple[str, ...]) -> list[str]:
        return [name for name in names if not str(data.get(name) or "").strip()]

    def list_cities(self, headers: dict) -> dict:
        principal = self._principal(headers)
        if not principal:
            return {"error": "unauthorized"}
        items = self.subjects.list_cities()
        if principal.get("role") == "super_admin":
            return {"items": items}
        items = [
            city
            for city in items
            if any(self._can_manage_district(principal, district["id"]) for district in self.subjects.list_districts_by_city(city["id"]))
        ]
        return {"items": items}

    def create_city(self, headers: dict, body: str | dict | None) -> dict:
        _, error = self._super_admin(headers)
        if error:
            return error
        data = _parse_json(body)
        missing = self._required(data, ("name",))
        if missing:
            return {"error": "required_fields", "fields": missing}
        return {"item": self.subjects.create_city(str(data["name"]).strip())}

    def deactivate_city(self, headers: dict, city_id: str) -> dict:
        _, error = self._super_admin(headers)
        if error:
            return error
        city = self.subjects.get_city(city_id)
        if not city or not city.get("is_active", True):
            return {"error": "not_found"}
        return {"item": self.subjects.deactivate_city(city_id)}

    def list_districts(self, headers: dict) -> dict:
        principal = self._principal(headers)
        if not principal:
            return {"error": "unauthorized"}
        items = self.subjects.list_districts()
        if principal.get("role") != "super_admin":
            items = [item for item in items if self._can_manage_district(principal, item["id"])]
        return {"items": items}

    def list_city_districts(self, headers: dict, city_id: str) -> dict:
        principal = self._principal(headers)
        if not principal:
            return {"error": "unauthorized"}
        city = self.subjects.get_city(city_id)
        if not city or not city.get("is_active", True):
            return {"error": "not_found"}
        items = self.subjects.list_districts_by_city(city_id)
        if principal.get("role") != "super_admin":
            items = [item for item in items if self._can_manage_district(principal, item["id"])]
        return {"items": items}

    def list_unassigned_districts(self, headers: dict) -> dict:
        _, error = self._super_admin(headers)
        if error:
            return error
        return {"items": self.subjects.list_unassigned_districts()}

    def create_city_district(self, headers: dict, city_id: str, body: str | dict | None) -> dict:
        _, error = self._super_admin(headers)
        if error:
            return error
        city = self.subjects.get_city(city_id)
        if not city or not city.get("is_active", True):
            return {"error": "not_found"}
        data = _parse_json(body)
        missing = self._required(data, ("name",))
        if missing:
            return {"error": "required_fields", "fields": missing}
        return {"item": self.subjects.create_district(str(data["name"]).strip(), city_id)}

    def assign_district_to_city(self, headers: dict, city_id: str, body: str | dict | None) -> dict:
        _, error = self._super_admin(headers)
        if error:
            return error
        data = _parse_json(body)
        district_id = str(data.get("district_id") or "").strip()
        city = self.subjects.get_city(city_id)
        district = self.subjects.get_district(district_id)
        if not city or not city.get("is_active", True) or not district or not district.get("is_active", True):
            return {"error": "not_found"}
        self.subjects.link_district_to_city(city_id, district_id)
        return {"item": district}

    def create_district(self, headers: dict, body: str | dict | None) -> dict:
        _, error = self._super_admin(headers)
        if error:
            return error
        return {"error": "city_required"}

    def list_houses(self, headers: dict, district_id: str) -> dict:
        _, error = self._authorized_district(headers, district_id)
        if error:
            return error
        return {"items": self.subjects.list_houses_by_district(district_id)}

    def create_house(self, headers: dict, district_id: str, body: str | dict | None) -> dict:
        _, error = self._authorized_district(headers, district_id)
        if error:
            return error
        data = _parse_json(body)
        missing = self._required(data, ("city", "street", "house_number"))
        if missing:
            return {"error": "required_fields", "fields": missing}
        return {
            "item": self.subjects.create_house(
                district_id,
                str(data["city"]).strip(),
                str(data["street"]).strip(),
                str(data["house_number"]).strip(),
                str(data.get("building") or "").strip(),
            )
        }

    def list_streets(self, headers: dict, district_id: str) -> dict:
        _, error = self._authorized_district(headers, district_id)
        if error:
            return error
        return {"items": self.subjects.list_streets_by_district(district_id)}

    def create_street(self, headers: dict, district_id: str, body: str | dict | None) -> dict:
        _, error = self._authorized_district(headers, district_id)
        if error:
            return error
        data = _parse_json(body)
        missing = self._required(data, ("name",))
        if missing:
            return {"error": "required_fields", "fields": missing}
        return {"item": self.subjects.create_street(district_id, str(data["name"]).strip())}

    def _authorized_street(self, headers: dict, street_id: str) -> tuple[dict | None, dict | None]:
        street = self.subjects.get_street(street_id)
        if not street or not street.get("is_active", True):
            return None, {"error": "not_found"}
        _, error = self._authorized_district(headers, street["district_id"])
        return (street, None) if not error else (None, error)

    def list_street_houses(self, headers: dict, street_id: str) -> dict:
        _, error = self._authorized_street(headers, street_id)
        if error:
            return error
        return {"items": self.subjects.list_houses_by_street(street_id)}

    def create_street_house(self, headers: dict, street_id: str, body: str | dict | None) -> dict:
        street, error = self._authorized_street(headers, street_id)
        if error:
            return error
        data = _parse_json(body)
        missing = self._required(data, ("house_number",))
        if missing:
            return {"error": "required_fields", "fields": missing}
        district = self.subjects.get_district(street["district_id"])
        city = self.subjects.get_city_for_district(street["district_id"])
        if not city or not city.get("is_active", True):
            return {"error": "city_required"}
        return {
            "item": self.subjects.create_house(
                district["id"],
                city["name"],
                street["name"],
                str(data["house_number"]).strip(),
                str(data.get("building") or "").strip(),
                street["id"],
            )
        }

    def _authorized_house(self, headers: dict, house_id: str) -> tuple[dict | None, dict | None]:
        house = self.subjects.get_house(house_id)
        if not house or not house.get("is_active", True):
            return None, {"error": "not_found"}
        _, error = self._authorized_district(headers, house["district_id"])
        return (house, None) if not error else (None, error)

    def list_entrances(self, headers: dict, house_id: str) -> dict:
        _, error = self._authorized_house(headers, house_id)
        if error:
            return error
        return {"items": [self._entrance_response(item) for item in self.subjects.list_entrances_by_house(house_id)]}

    def create_entrance(self, headers: dict, house_id: str, body: str | dict | None) -> dict:
        _, error = self._authorized_house(headers, house_id)
        if error:
            return error
        data = _parse_json(body)
        missing = self._required(data, ("entrance_number", "regioncity_external_ref"))
        if missing:
            return {"error": "required_fields", "fields": missing}
        public_code = str(data.get("public_code") or uuid4().hex[:12]).strip()
        external_ref = str(data.get("regioncity_external_ref") or "").strip()
        if len(public_code) > 80 or not all(character.isalnum() or character in "-_" for character in public_code):
            return {"error": "invalid_public_code"}
        if self.subjects.find_by_external_ref(external_ref):
            return {"error": "regioncity_map_object_id_conflict"}
        row = self.subjects.create_entrance(
            house_id,
            str(data["entrance_number"]).strip(),
            public_code,
            external_ref,
        )
        if not row:
            return {"error": "public_code_conflict"}
        return {"item": self._entrance_response(row)}

    def _entrance_response(self, item: dict) -> dict:
        result = dict(item)
        if self.public_site_url and item.get("public_code"):
            result["public_url"] = f"{self.public_site_url}/e/{item['public_code']}"
        if self.max_bot_deeplink_base and item.get("public_code"):
            result["max_bot_url"] = f"{self.max_bot_deeplink_base}?start=e_{item['public_code']}"
        return result

    def deactivate_district(self, headers: dict, district_id: str) -> dict:
        _, error = self._super_admin(headers)
        if error:
            return error
        district = self.subjects.get_district(district_id)
        if not district or not district.get("is_active", True):
            return {"error": "not_found"}
        return {"item": self.subjects.deactivate_district(district_id)}

    def deactivate_street(self, headers: dict, street_id: str) -> dict:
        street, error = self._authorized_street(headers, street_id)
        if error:
            return error
        return {"item": self.subjects.deactivate_street(street["id"])}

    def deactivate_house(self, headers: dict, house_id: str) -> dict:
        house, error = self._authorized_house(headers, house_id)
        if error:
            return error
        return {"item": self.subjects.deactivate_house(house["id"])}

    def deactivate_entrance(self, headers: dict, entrance_id: str) -> dict:
        entrance = self.subjects.get_entrance(entrance_id)
        if not entrance or not entrance.get("is_active", True):
            return {"error": "not_found"}
        _, error = self._authorized_house(headers, entrance["house_id"])
        if error:
            return error
        return {"item": self._entrance_response(self.subjects.deactivate_entrance(entrance_id))}

    @staticmethod
    def _norm(value: Any) -> str:
        return " ".join(str(value or "").strip().lower().replace("ё", "е").split())

    def _find_named(self, items: list[dict], name: str) -> dict | None:
        normalized = self._norm(name)
        return next((item for item in items if self._norm(item.get("name")) == normalized), None)

    def _find_house_in_street(self, street_id: str, house_number: str, building: str) -> dict | None:
        house_norm = self._norm(house_number)
        building_norm = self._norm(building)
        for house in self.subjects.list_houses_by_street(street_id):
            if self._norm(house.get("house_number")) == house_norm and self._norm(house.get("building")) == building_norm:
                return house
        return None

    def _find_entrance_in_house(self, house_id: str, entrance_number: str) -> dict | None:
        entrance_norm = self._norm(entrance_number)
        for entrance in self.subjects.list_entrances_by_house(house_id):
            if self._norm(entrance.get("entrance_number")) == entrance_norm:
                return entrance
        return None

    def _find_existing_address(self, row: dict) -> dict | None:
        city = self._find_named(self.subjects.list_cities(), row["city"])
        if not city:
            return None
        district = self._find_named(self.subjects.list_districts_by_city(city["id"]), row["district"])
        if not district:
            return None
        street = self._find_named(self.subjects.list_streets_by_district(district["id"]), row["street"])
        if not street:
            return None
        house = self._find_house_in_street(street["id"], row["house_number"], row.get("building", ""))
        if not house:
            return None
        entrance = self._find_entrance_in_house(house["id"], row["entrance_number"])
        return entrance

    def _address_rows_for_districts(self, districts: list[dict]) -> list[dict]:
        rows: list[dict] = []
        for district in districts:
            city = self.subjects.get_city_for_district(district["id"]) or {}
            for street in self.subjects.list_streets_by_district(district["id"]):
                for house in self.subjects.list_houses_by_street(street["id"]):
                    for entrance in self.subjects.list_entrances_by_house(house["id"]):
                        public_code = entrance.get("public_code", "")
                        rows.append(
                            {
                                "city": city.get("name") or house.get("city", ""),
                                "district": district.get("name", ""),
                                "street": street.get("name") or house.get("street", ""),
                                "house_number": house.get("house_number", ""),
                                "building": house.get("building", ""),
                                "entrance_number": entrance.get("entrance_number", ""),
                                "public_code": public_code,
                                "regioncity_map_object_id": entrance.get("regioncity_external_ref", ""),
                                "public_url": f"{self.public_site_url}/e/{public_code}" if self.public_site_url and public_code else "",
                                "max_bot_url": f"{self.max_bot_deeplink_base}?start=e_{public_code}" if self.max_bot_deeplink_base and public_code else "",
                            }
                        )
        rows.sort(key=lambda item: (self._norm(item["city"]), self._norm(item["district"]), self._norm(item["street"]), self._norm(item["house_number"]), self._norm(item["entrance_number"])))
        return rows

    def export_addresses(self, headers: dict) -> dict:
        principal = self._principal(headers)
        if not principal:
            return {"error": "unauthorized"}
        districts = self.subjects.list_districts()
        if principal.get("role") != "super_admin":
            districts = [district for district in districts if self._can_manage_district(principal, district["id"])]
        return {"items": self._address_rows_for_districts(districts)}

    def _normalize_import_row(self, row: dict) -> dict:
        return {
            "city": str(row.get("city") or "").strip(),
            "district": str(row.get("district") or "").strip(),
            "street": str(row.get("street") or "").strip(),
            "house_number": str(row.get("house_number") or "").strip(),
            "building": str(row.get("building") or "").strip(),
            "entrance_number": str(row.get("entrance_number") or "").strip(),
            "public_code": str(row.get("public_code") or "").strip(),
            "regioncity_map_object_id": str(row.get("regioncity_map_object_id") or row.get("regioncity_external_ref") or row.get("mapObjectID") or "").strip(),
        }

    def _preview_address_import(self, rows: list[dict]) -> list[dict]:
        public_codes: dict[str, int] = {}
        external_refs: dict[str, int] = {}
        result = []
        for index, source in enumerate(rows, start=1):
            row = self._normalize_import_row(source)
            errors: list[str] = []
            for field in ("city", "district", "street", "house_number", "entrance_number", "regioncity_map_object_id"):
                if not row[field]:
                    errors.append(f"{field}_required")
            if row["public_code"] and (len(row["public_code"]) > 80 or not all(character.isalnum() or character in "-_" for character in row["public_code"])):
                errors.append("invalid_public_code")
            if row["public_code"]:
                if row["public_code"] in public_codes:
                    errors.append(f"duplicate_public_code_row_{public_codes[row['public_code']]}")
                public_codes[row["public_code"]] = index
            if row["regioncity_map_object_id"]:
                if row["regioncity_map_object_id"] in external_refs:
                    errors.append(f"duplicate_regioncity_map_object_id_row_{external_refs[row['regioncity_map_object_id']]}")
                external_refs[row["regioncity_map_object_id"]] = index

            existing = self._find_existing_address(row) if not errors else None
            if row["public_code"]:
                subject = self.subjects.get_by_public_code(row["public_code"])
                if subject and (not existing or subject.subject_id != existing["id"]):
                    errors.append("public_code_conflict")
            if row["regioncity_map_object_id"]:
                subject = self.subjects.find_by_external_ref(row["regioncity_map_object_id"])
                if subject and (not existing or subject.subject_id != existing["id"]):
                    errors.append("regioncity_map_object_id_conflict")

            action = "update" if existing else "create"
            if errors:
                action = "error"
            result.append({"row_number": index, "action": action, "errors": errors, "item": row})
        return result

    def preview_address_import(self, headers: dict, body: str | dict | None) -> dict:
        _, error = self._super_admin(headers)
        if error:
            return error
        data = _parse_json(body)
        rows = data.get("items") or data.get("rows") or []
        if not isinstance(rows, list) or not rows:
            return {"error": "required_fields", "fields": ["items"]}
        return {"items": self._preview_address_import(rows)}

    def apply_address_import(self, headers: dict, body: str | dict | None) -> dict:
        _, error = self._super_admin(headers)
        if error:
            return error
        data = _parse_json(body)
        rows = data.get("items") or data.get("rows") or []
        if not isinstance(rows, list) or not rows:
            return {"error": "required_fields", "fields": ["items"]}
        preview = self._preview_address_import(rows)
        if any(item["errors"] for item in preview):
            return {"error": "import_has_errors", "items": preview}
        created = 0
        updated = 0
        for preview_item in preview:
            row = preview_item["item"]
            city = self._find_named(self.subjects.list_cities(), row["city"]) or self.subjects.create_city(row["city"])
            district = self._find_named(self.subjects.list_districts_by_city(city["id"]), row["district"])
            if not district:
                district = self._find_named(self.subjects.list_unassigned_districts(), row["district"]) or self.subjects.create_district(row["district"])
                self.subjects.link_district_to_city(city["id"], district["id"])
            street = self._find_named(self.subjects.list_streets_by_district(district["id"]), row["street"]) or self.subjects.create_street(district["id"], row["street"])
            house = self._find_house_in_street(street["id"], row["house_number"], row["building"]) or self.subjects.create_house(district["id"], city["name"], street["name"], row["house_number"], row["building"], street["id"])
            entrance = self._find_entrance_in_house(house["id"], row["entrance_number"])
            public_code = row["public_code"] or (entrance or {}).get("public_code") or uuid4().hex[:12]
            if entrance:
                self.subjects.update_entrance_refs(entrance["id"], public_code, row["regioncity_map_object_id"])
                updated += 1
            else:
                created_item = self.subjects.create_entrance(house["id"], row["entrance_number"], public_code, row["regioncity_map_object_id"])
                if not created_item:
                    return {"error": "public_code_conflict", "items": preview}
                created += 1
        return {"created": created, "updated": updated, "items": preview}

    @staticmethod
    def _candidate_value(item: dict, *keys: str) -> str:
        for key in keys:
            value = item.get(key)
            if value:
                return str(value)
        return ""

    def _address_score(self, requested: str, candidate: str) -> float:
        left = self._norm(requested)
        right = self._norm(candidate)
        if not left or not right:
            return 0.0
        ratio = SequenceMatcher(None, left, right).ratio()
        left_tokens = set(left.split())
        right_tokens = set(right.split())
        overlap = len(left_tokens & right_tokens) / max(len(left_tokens), 1)
        return round(max(ratio, overlap), 3)

    def search_regioncity_map_objects(self, headers: dict, params: dict) -> dict:
        principal = self._principal(headers)
        if not principal:
            return {"error": "unauthorized"}
        address = str(params.get("address") or "").strip()
        if not address:
            return {"error": "required_fields", "fields": ["address"]}
        if not self.regioncity_client:
            return {"error": "configuration_error"}
        try:
            items = asyncio.run(self.regioncity_client.list_map_objects(self.regioncity_map_objects_path, address=address))
        except Exception:
            return {"error": "regioncity_unavailable"}
        candidates = []
        for item in items:
            map_object_id = self._candidate_value(item, "mapObjectID", "objectID", "id")
            candidate_address = self._candidate_value(item, "address", "fullAddress", "displayAddress")
            if not map_object_id or not candidate_address:
                continue
            score = self._address_score(address, candidate_address)
            candidates.append(
                {
                    "map_object_id": map_object_id,
                    "address": candidate_address,
                    "title": self._candidate_value(item, "title", "name", "objectName"),
                    "object_type": self._candidate_value(item, "objectType", "type", "mapObjectType"),
                    "score": score,
                }
            )
        candidates.sort(key=lambda item: item["score"], reverse=True)
        return {"items": candidates[:10]}

    def list_resident_users(self, headers: dict) -> dict:
        _, error = self._super_admin(headers)
        if error:
            return error
        return {"items": self.users.list_active_for_admin()}

    def deactivate_resident_user(self, headers: dict, user_id: str) -> dict:
        _, error = self._super_admin(headers)
        if error:
            return error
        item = self.users.deactivate_for_admin(user_id)
        if not item:
            return {"error": "not_found"}
        self.subscriptions.deactivate_all(user_id)
        return {"item": item}

    def list_admin_users(self, headers: dict) -> dict:
        _, error = self._super_admin(headers)
        if error:
            return error
        items = []
        for item in self.admin_repo.list_active_for_admin():
            result = dict(item)
            result["district_ids"] = self.permissions.list_district_ids(item["id"])
            items.append(result)
        return {"items": items}

    def create_admin_user(self, headers: dict, body: str | dict | None) -> dict:
        _, error = self._super_admin(headers)
        if error:
            return error
        data = _parse_json(body)
        login = str(data.get("login") or "").strip()
        password = str(data.get("password") or "")
        role = str(data.get("role") or "").strip()
        district_ids = [str(item).strip() for item in (data.get("district_ids") or []) if str(item).strip()]
        if not login or len(password) < 12 or role not in {"super_admin", "district_admin"}:
            return {"error": "invalid_admin_user"}
        if role == "district_admin" and not district_ids:
            return {"error": "district_required"}
        if self.admin_repo.find_any_by_login(login):
            return {"error": "login_conflict"}
        for district_id in district_ids:
            if not self.subjects.get_district(district_id):
                return {"error": "not_found"}
        item = self.admin_repo.create_for_admin(login, self.hash_password(password), role)
        if role == "district_admin":
            self.permissions.grant_districts(item["id"], district_ids)
            item["district_ids"] = district_ids
        else:
            item["district_ids"] = []
        return {"item": item}

    def deactivate_admin_user(self, headers: dict, admin_id: str) -> dict:
        principal, error = self._super_admin(headers)
        if error:
            return error
        if principal.get("sub") == admin_id:
            return {"error": "cannot_deactivate_self"}
        item = self.admin_repo.deactivate_for_admin(admin_id)
        return {"item": item} if item else {"error": "not_found"}

    def send_test_notification(self, headers: dict, body: str | dict | None) -> dict:
        if "error" in self.me(headers):
            return {"error": "unauthorized"}
        data = _parse_json(body)
        user_id = str(data.get("user_id") or "").strip()
        if not user_id:
            return {"error": "user_id_required"}
        event = TaskEvent(
            external_id=f"admin-test-{uuid4()}",
            subject_id="admin-test",
            source=Source.SYSTEM,
            event_type=EventType.TEST_NOTIFICATION,
            occurred_at=datetime.now(UTC),
            metadata={"subject_title": str(data.get("subject_title") or "test subject")},
        )
        return {"sent": self.notifier.notify_users(event, [user_id])}


class BotService:
    def __init__(self, users, subjects, subscriptions, sub_uc, list_uc, disable_uc, public_site_url: str = ""):
        self.users = users
        self.subjects = subjects
        self.subscriptions = subscriptions
        self.sub_uc = sub_uc
        self.list_uc = list_uc
        self.disable_uc = disable_uc
        self.address_picker_url = f"{public_site_url.rstrip('/')}/?view=select" if public_site_url else ""
        self.webhook_parser = MaxWebhookParser()

    def handle_payload(self, payload: dict):
        text = self.webhook_parser.message_text(payload)
        start_payload = self.webhook_parser.bot_start_payload(payload)
        if start_payload:
            ext_user = self.webhook_parser.external_user_id(payload) or "unknown"
            user = self.users.get_or_create_channel_user("max", ext_user, self.webhook_parser.display_name(payload))
            if start_payload.startswith("e_"):
                return self._subscribe_by_public_code(user.user_id, start_payload[2:])
            return self._welcome()
        action = self.webhook_parser.callback_payload(payload)
        ext_user = self.webhook_parser.external_user_id(payload) or "unknown"
        user = self.users.get_or_create_channel_user("max", ext_user, self.webhook_parser.display_name(payload))

        if action:
            return self._handle_action(user.user_id, action)

        if text.startswith("/start"):
            arg = text.replace("/start", "", 1).strip()
            if arg.startswith("e_"):
                arg = arg[2:]
            if arg:
                return self._subscribe_by_public_code(user.user_id, arg)
            return self._welcome()

        command = self._normalize(text)
        subscribe_code = self._subscription_code(text)
        if subscribe_code:
            return self._subscribe_by_public_code(user.user_id, subscribe_code)

        if command in {"мои адреса", "адреса", "подписки", "my_subscriptions", "/list"}:
            return self._list_subscriptions(user.user_id)

        if command in {"подписаться", "добавить адрес", "добавить", "/subscribe"}:
            return self._subscribe_help()

        if command in {"отписаться", "удалить адрес", "remove_subscription"}:
            return self._unsubscribe_help(user.user_id)

        if command in {"отключить все", "отписаться от всего", "удалить все", "disable_all"}:
            return {
                "message": "Массовая отписка недоступна, чтобы случайно не удалить все адреса. Откройте «Мои адреса» и выберите конкретный адрес.",
                "keyboard": self._subscription_keyboard(user.user_id),
            }

        if command in {"услуги", "сервисы", "services"}:
            return {
                "message": "Раздел услуг пока зарезервирован. Сейчас бот отправляет уведомления по выбранным адресам.",
                "keyboard": self._main_keyboard(),
            }

        if command in {"помощь", "help", "/help", "меню", "menu"}:
            return self._help()

        unsubscribe_target = self._unsubscribe_target(text)
        if unsubscribe_target:
            return self._unsubscribe(user.user_id, unsubscribe_target)

        return {
            "message": "Не понял команду. Выберите действие кнопкой ниже или напишите «Помощь».",
            "keyboard": self._main_keyboard(),
        }

    def _handle_action(self, user_id: str, action: str) -> dict:
        if action == "menu:main":
            return {"message": "Выберите действие:", "keyboard": self._main_keyboard()}
        if action == "menu:addresses":
            return self._list_subscriptions(user_id)
        if action == "menu:choose_address":
            return self._subscribe_help()
        if action == "menu:services":
            return {
                "message": "Раздел услуг пока зарезервирован. Сейчас бот отправляет уведомления по выбранным адресам.",
                "keyboard": self._main_keyboard(),
            }
        if action == "menu:help":
            return self._help()
        if action.startswith("address:open:"):
            return self._open_subscription(user_id, action.removeprefix("address:open:"))
        if action.startswith("address:unsubscribe:"):
            return self._confirm_unsubscribe(user_id, action.removeprefix("address:unsubscribe:"))
        if action.startswith("address:unsubscribe_confirm:"):
            return self._unsubscribe_subscription(user_id, action.removeprefix("address:unsubscribe_confirm:"))
        return {"message": "Не понял действие. Вернитесь в меню и попробуйте снова.", "keyboard": self._main_keyboard()}

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.strip().lower().split())

    @staticmethod
    def _callback_button(text: str, payload: str, intent: str = "default") -> dict:
        return {"type": "callback", "text": text, "payload": payload, "intent": intent}

    @staticmethod
    def _link_button(text: str, url: str) -> dict:
        return {"type": "link", "text": text, "url": url}

    def _main_keyboard(self) -> list[list[dict]]:
        rows: list[list[dict]] = []
        if self.address_picker_url:
            rows.append([self._link_button("Выбрать адрес", self.address_picker_url)])
        else:
            rows.append([self._callback_button("Выбрать адрес", "menu:choose_address")])
        rows.append([self._callback_button("Мои адреса", "menu:addresses")])
        rows.append([self._callback_button("Услуги", "menu:services"), self._callback_button("Помощь", "menu:help")])
        return rows

    def _welcome(self) -> dict:
        return {
            "message": (
                "Здравствуйте. Я буду присылать уведомления по вашим адресам.\n\n"
                "Как начать:\n"
                "1. Откройте QR-код у нужного подъезда или публичную страницу адреса.\n"
                "2. Нажмите «Перейти в MAX».\n"
                "3. Бот сам добавит адрес в ваши подписки.\n\n"
                "Также можно нажать «Выбрать адрес» и найти адрес прямо из меню бота.\n\n"
                "Квартиру указывать не нужно."
            ),
            "keyboard": self._main_keyboard(),
        }

    def _help(self) -> dict:
        return {
            "message": (
                "Что можно сделать:\n"
                "• «Выбрать адрес» — найти поддерживаемый адрес в списке и подписаться.\n"
                "• «Мои адреса» — посмотреть активные подписки и выбрать адрес для управления.\n"
                "• «Отписаться 1» — текстовая команда для отписки по номеру из списка, если кнопки недоступны.\n"
                "• «Услуги» — будущие сервисы платформы."
            ),
            "keyboard": self._main_keyboard(),
        }

    def _subscribe_help(self) -> dict:
        return {
            "message": (
                "Нажмите «Выбрать адрес» и найдите адрес в списке.\n\n"
                "Еще можно отсканировать QR-код у подъезда или открыть публичную страницу адреса "
                "и нажать «Перейти в MAX».\n\n"
                "Если у вас уже есть код из ссылки, отправьте: «Подписаться КОД»."
            ),
            "keyboard": self._main_keyboard(),
        }

    def _subscription_code(self, text: str) -> str | None:
        stripped = text.strip()
        lowered = self._normalize(stripped)
        prefixes = ("подписаться ", "/subscribe ", "subscribe ", "+ ")
        for prefix in prefixes:
            if lowered.startswith(prefix):
                return stripped[len(prefix) :].strip()
        return None

    def _subscribe_by_public_code(self, user_id: str, code: str) -> dict:
        clean_code = code.strip()
        if clean_code.startswith("e_"):
            clean_code = clean_code[2:]
        subject = self.subjects.get_by_public_code(clean_code)
        if not subject:
            return {
                "message": "Не нашел этот адрес. Проверьте ссылку или отсканируйте QR-код еще раз.",
                "keyboard": self._main_keyboard(),
            }
        if self.subscriptions.get_active(user_id, subject.subject_id):
            return {
                "message": f"Вы уже подписаны на этот адрес:\n{subject.title}",
                "keyboard": self._subscription_keyboard(user_id),
            }
        self.sub_uc.execute(Subscription(subscription_id=str(uuid4()), user_id=user_id, subject_id=subject.subject_id))
        return {
            "message": f"Готово. Теперь вы будете получать уведомления по адресу:\n{subject.title}",
            "keyboard": self._subscription_keyboard(user_id),
        }

    def _active_subjects(self, user_id: str) -> list[tuple[Subscription, Any]]:
        items = []
        for subscription in self.list_uc.execute(user_id):
            subject = self.subjects.get_by_id(subscription.subject_id)
            if subject and subject.is_active:
                items.append((subscription, subject))
        return items

    def _list_subscriptions(self, user_id: str) -> dict:
        items = self._active_subjects(user_id)
        if not items:
            return {
                "message": "У вас пока нет адресов. Нажмите «Выбрать адрес» или откройте QR-код подъезда и нажмите «Перейти в MAX».",
                "keyboard": self._main_keyboard(),
            }
        lines = ["Ваши адреса:"]
        for number, (_, subject) in enumerate(items, start=1):
            lines.append(f"{number}. {subject.title}")
        lines.append("")
        lines.append("Выберите адрес для управления.")
        return {"message": "\n".join(lines), "keyboard": self._subscription_keyboard(user_id)}

    def _subscription_keyboard(self, user_id: str) -> list[list[dict]]:
        items = self._active_subjects(user_id)
        buttons = [
            [self._callback_button(f"{number}. {self._short_title(subject.title)}", f"address:open:{subscription.subscription_id}")]
            for number, (subscription, subject) in enumerate(items, start=1)
        ]
        if self.address_picker_url:
            buttons.append([self._link_button("Выбрать адрес", self.address_picker_url)])
        else:
            buttons.append([self._callback_button("Выбрать адрес", "menu:choose_address")])
        buttons.append([self._callback_button("Помощь", "menu:help"), self._callback_button("Назад", "menu:main")])
        return buttons

    @staticmethod
    def _short_title(title: str, limit: int = 54) -> str:
        return title if len(title) <= limit else f"{title[: limit - 1].rstrip()}…"

    def _unsubscribe_target(self, text: str) -> str | None:
        stripped = text.strip()
        lowered = self._normalize(stripped)
        prefixes = ("отписаться ", "удалить ", "отключить ", "/unsubscribe ", "unsubscribe ")
        for prefix in prefixes:
            if lowered.startswith(prefix):
                return stripped[len(prefix) :].strip()
        return None

    def _unsubscribe_help(self, user_id: str) -> dict:
        items = self._active_subjects(user_id)
        if not items:
            return {"message": "Активных подписок пока нет.", "keyboard": self._main_keyboard()}
        return self._list_subscriptions(user_id)

    def _unsubscribe(self, user_id: str, target: str) -> dict:
        items = self._active_subjects(user_id)
        if not items:
            return {"message": "Активных подписок пока нет.", "keyboard": self._main_keyboard()}
        subject = None
        if target.isdigit():
            index = int(target)
            if 1 <= index <= len(items):
                subject = items[index - 1][1]
        else:
            subject = self.subjects.get_by_public_code(target)
        if not subject:
            return {
                "message": "Не понял, какой адрес отключить. Нажмите «Мои адреса» и выберите номер из списка.",
                "keyboard": self._subscription_keyboard(user_id),
            }
        self.subscriptions.deactivate(user_id, subject.subject_id)
        return {"message": f"Вы отписались от адреса:\n{subject.title}", "keyboard": self._subscription_keyboard(user_id)}

    def _subscription_item(self, user_id: str, subscription_id: str) -> tuple[Subscription, Any] | None:
        for subscription, subject in self._active_subjects(user_id):
            if subscription.subscription_id == subscription_id:
                return subscription, subject
        return None

    def _open_subscription(self, user_id: str, subscription_id: str) -> dict:
        item = self._subscription_item(user_id, subscription_id)
        if not item:
            return {
                "message": "Этот адрес больше не найден в ваших подписках. Обновите список адресов.",
                "keyboard": self._subscription_keyboard(user_id),
            }
        subscription, subject = item
        return {
            "message": (
                "Адрес:\n"
                f"{subject.title}\n\n"
                "Вы можете отписаться от этого адреса. После отписки уведомления по нему приходить не будут."
            ),
            "keyboard": self._address_keyboard(subscription.subscription_id),
        }

    def _address_keyboard(self, subscription_id: str) -> list[list[dict]]:
        return [
            [self._callback_button("Отписаться от адреса", f"address:unsubscribe:{subscription_id}", "negative")],
            [self._callback_button("Назад к моим адресам", "menu:addresses")],
            [self._callback_button("Помощь", "menu:help")],
        ]

    def _confirm_unsubscribe(self, user_id: str, subscription_id: str) -> dict:
        item = self._subscription_item(user_id, subscription_id)
        if not item:
            return {
                "message": "Этот адрес больше не найден в ваших подписках. Обновите список адресов.",
                "keyboard": self._subscription_keyboard(user_id),
            }
        _, subject = item
        return {
            "message": f"Подтвердите отписку от адреса:\n{subject.title}",
            "keyboard": [
                [self._callback_button("Да, отписаться", f"address:unsubscribe_confirm:{subscription_id}", "negative")],
                [self._callback_button("Отмена", f"address:open:{subscription_id}")],
            ],
        }

    def _unsubscribe_subscription(self, user_id: str, subscription_id: str) -> dict:
        item = self._subscription_item(user_id, subscription_id)
        if not item:
            return {
                "message": "Этот адрес уже не активен в ваших подписках.",
                "keyboard": self._subscription_keyboard(user_id),
            }
        _, subject = item
        self.subscriptions.deactivate(user_id, subject.subject_id)
        return {"message": f"Вы отписались от адреса:\n{subject.title}", "keyboard": self._subscription_keyboard(user_id)}


class _Mock:
    def __getattr__(self, item):
        def _(*args, **kwargs):
            return {"mock": True, "action": item}

        return _


def _parse_json(body: str | dict | None) -> dict:
    if isinstance(body, dict):
        return body
    if not body:
        return {}
    return json.loads(body)


def build_container() -> AppContainer:
    if os.getenv("ENV", "local") == "local" or os.getenv("USE_MOCKS", "false").lower() == "true":
        m = _Mock()
        return AppContainer(bot_service=m, public_service=m, admin_service=m, polling_use_case=m, notification_service=m)

    settings = load_settings()
    ydb = YdbClient(YdbConfig(settings.ydb_endpoint, settings.ydb_database))
    session = ydb.session()

    subjects = YdbSubjectRepository(session)
    users = YdbUserRepository(session)
    subscriptions = YdbSubscriptionRepository(session)
    processed = YdbProcessedEventRepository(session)
    admin_users = YdbAdminUserRepository(session)
    admin_permissions = YdbAdminPermissionRepository(session)
    _ = YdbFeatureFlagRepository(session)

    secret = YandexLockboxSecretProvider(settings.env)
    max_channel = MaxNotificationChannel(MaxClient(secret, settings.max_api_base_url))
    regioncity_client = RegionCityClient(secret, settings.regioncity_base_url)
    notifier = NotificationService(processed, _Registry(max_channel), CodeTemplateProvider())

    return AppContainer(
        bot_service=BotService(
            users,
            subjects,
            subscriptions,
            SubscribeUserToSubjectUseCase(subjects, subscriptions),
            ListUserSubscriptionsUseCase(subscriptions),
            DisableAllUserNotificationsUseCase(subscriptions),
            settings.public_site_url,
        ),
        public_service=PublicService(
            subjects,
            users,
            subscriptions,
            SubscribeUserToSubjectUseCase(subjects, subscriptions),
            secret,
            settings.max_bot_deeplink_base,
        ),
        admin_service=AdminService(
            admin_users,
            admin_permissions,
            subjects,
            users,
            subscriptions,
            secret,
            notifier,
            session,
            settings.public_site_url,
            settings.max_bot_deeplink_base,
            regioncity_client,
            settings.regioncity_map_objects_path,
        ),
        polling_use_case=_Mock(),
        notification_service=notifier,
        bot_reply_channel=max_channel,
    )


def api_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False, default=lambda value: value.isoformat() if isinstance(value, datetime) else str(value)),
    }


def now_utc() -> datetime:
    return datetime.now(UTC)
