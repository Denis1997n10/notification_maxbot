from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.value_objects.enums import AdminRole, ChannelType, EventType, Source, SubjectType


@dataclass(slots=True)
class User:
    user_id: str
    channel: ChannelType = ChannelType.MAX
    notifications_enabled: bool = True
    is_active: bool = True


@dataclass(slots=True)
class Subject:
    subject_id: str
    subject_type: SubjectType
    title: str
    is_active: bool = True
    external_ref: str | None = None


@dataclass(slots=True)
class Subscription:
    subscription_id: str
    user_id: str
    subject_id: str
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now())


@dataclass(slots=True)
class TaskImage:
    url: str
    label: str | None = None


@dataclass(slots=True)
class TaskEvent:
    external_id: str
    subject_id: str
    source: Source
    event_type: EventType
    occurred_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    images: list[TaskImage] = field(default_factory=list)


@dataclass(slots=True)
class NotificationPayload:
    user_id: str
    channel: ChannelType | str
    title: str
    body: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FeatureFlag:
    key: str
    enabled: bool


@dataclass(slots=True)
class AdminUser:
    admin_id: str
    role: AdminRole
    district_ids: list[str] = field(default_factory=list)
