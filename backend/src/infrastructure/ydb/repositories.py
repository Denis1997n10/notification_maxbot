from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

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


class YdbUserRepository(UserRepository):
    def __init__(self, session: YdbSession) -> None: self.session = session
    def get_by_id(self, user_id: str) -> User | None: return None
    def save(self, user: User) -> None: self.session.execute("UPSERT INTO users ...", {"user_id": user.user_id})


class YdbSubjectRepository(SubjectRepository):
    def __init__(self, session: YdbSession) -> None: self.session = session
    def get_by_id(self, subject_id: str) -> Subject | None: return None
    def get_by_public_code(self, public_code: str) -> Subject | None:
        rows = self.session.execute("SELECT * FROM entrances WHERE public_code=$code AND is_active=true LIMIT 1", {"$code": public_code})
        return self._map_entrance(rows[0]) if rows else None
    def find_by_external_ref(self, external_ref: str) -> Subject | None:
        rows = self.session.execute("SELECT * FROM entrances WHERE regioncity_external_ref=$ref AND is_active=true LIMIT 1", {"$ref": external_ref})
        return self._map_entrance(rows[0]) if rows else None
    def list_active(self) -> list[Subject]: return []
    def _map_entrance(self, row: dict) -> Subject:
        return Subject(subject_id=row["entrance_id"], subject_type=SubjectType.ENTRANCE, title=row.get("title", ""), is_active=row.get("is_active", True), external_ref=row.get("regioncity_external_ref"))


class YdbSubscriptionRepository(SubscriptionRepository):
    def __init__(self, session: YdbSession) -> None: self.session = session
    def list_active_by_user(self, user_id: str) -> list[Subscription]: return []
    def get_active(self, user_id: str, subject_id: str) -> Subscription | None: return None
    def save(self, subscription: Subscription) -> None: self.session.execute("UPSERT INTO subscriptions ...", {})
    def deactivate(self, user_id: str, subject_id: str) -> None: self.session.execute("UPDATE subscriptions SET is_active=false ...", {})
    def deactivate_all(self, user_id: str) -> int: self.session.execute("UPDATE subscriptions SET is_active=false ...", {}); return 0


class YdbProcessedEventRepository(ProcessedEventRepository):
    def __init__(self, session: YdbSession) -> None: self.session = session
    def is_processed(self, source: str, external_id: str, event_type: str) -> bool:
        rows = self.session.execute("SELECT external_id FROM processed_events WHERE source=$source AND external_id=$external_id AND event_type=$event_type LIMIT 1", {"$source": source, "$external_id": external_id, "$event_type": event_type})
        return bool(rows)
    def mark_processed(self, source: str, external_id: str, event_type: str, processed_at: datetime) -> None:
        self.session.execute("UPSERT INTO processed_events (source, external_id, event_type, processed_at) VALUES ($source,$external_id,$event_type,$processed_at)", {"$source": source, "$external_id": external_id, "$event_type": event_type, "$processed_at": processed_at.isoformat()})


class YdbFeatureFlagRepository(FeatureFlagRepository):
    def __init__(self, session: YdbSession) -> None: self.session = session
    def is_enabled(self, key: str) -> bool: return False


class YdbUserFeatureFlagRepository(UserFeatureFlagRepository):
    def __init__(self, session: YdbSession) -> None: self.session = session
    def is_enabled_for_user(self, user_id: str, key: str) -> bool: return False


class YdbAdminUserRepository(AdminUserRepository):
    def __init__(self, session: YdbSession) -> None: self.session = session
    def get_by_id(self, admin_id: str) -> AdminUser | None: return AdminUser(admin_id=admin_id, role=AdminRole.DISTRICT_ADMIN)


class YdbAdminPermissionRepository(AdminPermissionRepository):
    def __init__(self, session: YdbSession) -> None: self.session = session
    def can_manage_subject(self, admin_id: str, district_id: str) -> bool: return False


class YdbPublicPageCacheRepository(PublicPageCacheRepository):
    def __init__(self, session: YdbSession) -> None: self.session = session
    def get(self, key: str):
        rows = self.session.execute("SELECT payload_json, expires_at FROM public_page_cache WHERE cache_key=$key LIMIT 1", {"$key": key})
        if not rows:
            return None
        row = rows[0]
        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at < datetime.now(UTC):
            return None
        return json.loads(row["payload_json"])
    def set(self, key: str, value: dict, ttl_seconds: int) -> None:
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        self.session.execute("UPSERT INTO public_page_cache (cache_key, payload_json, expires_at) VALUES ($k,$p,$e)", {"$k": key, "$p": json.dumps(value), "$e": expires_at.isoformat()})
