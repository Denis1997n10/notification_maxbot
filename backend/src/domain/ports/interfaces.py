from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from domain.entities.models import AdminUser, NotificationPayload, Subject, Subscription, TaskEvent, User


class UserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: str) -> User | None: ...

    @abstractmethod
    def save(self, user: User) -> None: ...


class SubjectRepository(ABC):
    @abstractmethod
    def get_by_id(self, subject_id: str) -> Subject | None: ...

    @abstractmethod
    def get_by_public_code(self, public_code: str) -> Subject | None: ...

    @abstractmethod
    def find_by_external_ref(self, external_ref: str) -> Subject | None: ...

    @abstractmethod
    def list_active(self) -> list[Subject]: ...


class SubscriptionRepository(ABC):
    @abstractmethod
    def list_active_by_user(self, user_id: str) -> list[Subscription]: ...

    @abstractmethod
    def get_active(self, user_id: str, subject_id: str) -> Subscription | None: ...

    @abstractmethod
    def save(self, subscription: Subscription) -> None: ...

    @abstractmethod
    def deactivate(self, user_id: str, subject_id: str) -> None: ...

    @abstractmethod
    def deactivate_all(self, user_id: str) -> int: ...


class ProcessedEventRepository(ABC):
    @abstractmethod
    def is_processed(self, source: str, external_id: str, event_type: str) -> bool: ...

    @abstractmethod
    def mark_processed(self, source: str, external_id: str, event_type: str, processed_at: datetime) -> None: ...


class FeatureFlagRepository(ABC):
    @abstractmethod
    def is_enabled(self, key: str) -> bool: ...


class UserFeatureFlagRepository(ABC):
    @abstractmethod
    def is_enabled_for_user(self, user_id: str, key: str) -> bool: ...


class AdminUserRepository(ABC):
    @abstractmethod
    def get_by_id(self, admin_id: str) -> AdminUser | None: ...


class AdminPermissionRepository(ABC):
    @abstractmethod
    def can_manage_subject(self, admin_id: str, district_id: str) -> bool: ...


class PublicPageCacheRepository(ABC):
    @abstractmethod
    def get(self, key: str): ...

    @abstractmethod
    def set(self, key: str, value: dict, ttl_seconds: int) -> None: ...


class ExternalTaskProvider(ABC):
    @abstractmethod
    def fetch_events(self) -> list[TaskEvent]: ...


class NotificationChannel(ABC):
    @abstractmethod
    def send(self, payload: NotificationPayload) -> None: ...


class NotificationChannelRegistry(ABC):
    @abstractmethod
    def get(self, name: str) -> NotificationChannel: ...


class ImageLoader(ABC):
    @abstractmethod
    def load(self, event: TaskEvent) -> list[str]: ...


class TemplateProvider(ABC):
    @abstractmethod
    def render(self, template_key: str, channel: str, context: dict) -> tuple[str, str]: ...


class SecretProvider(ABC):
    @abstractmethod
    def get_secret(self, key: str) -> str: ...


class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, raw_password: str) -> str: ...


class TokenService(ABC):
    @abstractmethod
    def issue(self, subject: str) -> str: ...
