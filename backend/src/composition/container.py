from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import hmac
import json
import os
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
from domain.entities.models import Subscription
from infrastructure.lockbox.secret_provider import YandexLockboxSecretProvider
from infrastructure.max.max_client import MaxClient
from infrastructure.max.max_notification_channel import MaxNotificationChannel
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
    def __init__(self, admin_repo: YdbAdminUserRepository, jwt_secret: str):
        self.admin_repo = admin_repo
        self.jwt_secret = jwt_secret.encode()

    def _hash_password(self, raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    def _issue(self, admin_id: str, role: str) -> str:
        payload = json.dumps({"sub": admin_id, "role": role}, ensure_ascii=False)
        sig = hmac.new(self.jwt_secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{sig}"

    def _verify(self, token: str) -> dict:
        payload, sig = token.rsplit(".", 1)
        expected = hmac.new(self.jwt_secret, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("invalid token")
        return json.loads(payload)

    def login(self, body: str | dict | None):
        d = _parse_json(body)
        u = self.admin_repo.find_by_login(d.get("login", ""))
        if not u or u["password_hash"] != self._hash_password(d.get("password", "")):
            return {"error": "invalid_credentials"}
        return {"token": self._issue(u["id"], u["role"]), "role": u["role"]}

    def me(self, headers: dict):
        auth = headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return {"error": "unauthorized"}
        try:
            return self._verify(auth.replace("Bearer ", ""))
        except Exception:
            return {"error": "unauthorized"}


class BotService:
    def __init__(self, users, subjects, subscriptions, sub_uc, list_uc, disable_uc):
        self.users = users
        self.subjects = subjects
        self.subscriptions = subscriptions
        self.sub_uc = sub_uc
        self.list_uc = list_uc
        self.disable_uc = disable_uc

    def handle_payload(self, payload: dict):
        text = ((payload.get("message") or {}).get("text") or payload.get("text") or "").strip()
        ext_user = str((payload.get("user") or {}).get("id") or payload.get("user_id") or payload.get("chat_id") or "unknown")
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
    _ = YdbAdminPermissionRepository(session)
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
        admin_service=AdminService(admin_users, os.getenv("ADMIN_JWT_SECRET", "dev-secret")),
        polling_use_case=_Mock(),
        notification_service=notifier,
    )


def api_response(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body, ensure_ascii=False)}


def now_utc() -> datetime:
    return datetime.now(UTC)
