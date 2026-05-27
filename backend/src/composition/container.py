from __future__ import annotations

from dataclasses import dataclass
import base64
from datetime import UTC, datetime, timedelta
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
from infrastructure.max.max_webhook_parser import MaxWebhookParser
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
    def __init__(self, subjects: YdbSubjectRepository):
        self.subjects = subjects

    def list_districts(self):
        return self.subjects.list_districts()

    def list_houses(self, district_id: str):
        return self.subjects.list_houses_by_district(district_id)

    def list_entrances(self, house_id: str):
        return self.subjects.list_entrances_by_house(house_id)

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
            "max_bot_link": f"/start e_{public_code}",
            "events": [],
            "mock": False,
        }


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
        missing = self._required(data, ("entrance_number",))
        if missing:
            return {"error": "required_fields", "fields": missing}
        public_code = str(data.get("public_code") or uuid4().hex[:12]).strip()
        if len(public_code) > 80 or not all(character.isalnum() or character in "-_" for character in public_code):
            return {"error": "invalid_public_code"}
        row = self.subjects.create_entrance(
            house_id,
            str(data["entrance_number"]).strip(),
            public_code,
            str(data.get("regioncity_external_ref") or "").strip(),
        )
        if not row:
            return {"error": "public_code_conflict"}
        return {"item": self._entrance_response(row)}

    def _entrance_response(self, item: dict) -> dict:
        result = dict(item)
        if self.public_site_url and item.get("public_code"):
            result["public_url"] = f"{self.public_site_url}/e/{item['public_code']}"
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
    def __init__(self, users, subjects, subscriptions, sub_uc, list_uc, disable_uc):
        self.users = users
        self.subjects = subjects
        self.subscriptions = subscriptions
        self.sub_uc = sub_uc
        self.list_uc = list_uc
        self.disable_uc = disable_uc
        self.webhook_parser = MaxWebhookParser()

    def handle_payload(self, payload: dict):
        text = self.webhook_parser.message_text(payload)
        ext_user = self.webhook_parser.external_user_id(payload) or "unknown"
        user = self.users.get_or_create_channel_user("max", ext_user, (payload.get("user") or {}).get("name", ""))

        if text.startswith("/start"):
            arg = text.replace("/start", "", 1).strip()
            if arg.startswith("e_"):
                arg = arg[2:]
            if arg:
                s = self.subjects.get_by_public_code(arg)
                if not s:
                    return {"message": "Адрес не найден"}
                return {"message": f"Вы хотите получать уведомления по адресу: {s.title}? Ответьте: Подписаться {arg}"}
            return {"message": "Добро пожаловать! Команды: Мои адреса, Отключить все"}

        if text.startswith("Подписаться "):
            code = text.split(" ", 1)[1].strip()
            s = self.subjects.get_by_public_code(code)
            if not s:
                return {"message": "Адрес не найден"}
            if self.subscriptions.get_active(user.user_id, s.subject_id):
                return {"message": "Вы уже подписаны"}
            self.sub_uc.execute(Subscription(subscription_id=str(uuid4()), user_id=user.user_id, subject_id=s.subject_id))
            return {"message": "Подписка оформлена"}

        if text in {"Мои адреса", "my_subscriptions"}:
            subs = self.list_uc.execute(user.user_id)
            return {"message": f"Подписок: {len(subs)}"}

        if text in {"Отключить все", "disable_all"}:
            n = self.disable_uc.execute(user.user_id)
            return {"message": f"Отключено: {n}"}

        if text in {"Услуги", "services"}:
            return {"message": "Скоро здесь можно будет заказать дополнительные услуги"}

        return {"message": "help"}


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
    notifier = NotificationService(processed, _Registry(max_channel), CodeTemplateProvider())

    return AppContainer(
        bot_service=BotService(
            users,
            subjects,
            subscriptions,
            SubscribeUserToSubjectUseCase(subjects, subscriptions),
            ListUserSubscriptionsUseCase(subscriptions),
            DisableAllUserNotificationsUseCase(subscriptions),
        ),
        public_service=PublicService(subjects),
        admin_service=AdminService(admin_users, admin_permissions, subjects, users, subscriptions, secret, notifier, session, settings.public_site_url),
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
