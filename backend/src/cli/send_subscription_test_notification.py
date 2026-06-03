from __future__ import annotations

import argparse
import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

from application.services import NotificationService
from application.templates.code_template_provider import CodeTemplateProvider
from config.settings import load_settings
from domain.entities.models import TaskEvent
from domain.value_objects.enums import EventType, Source
from infrastructure.lockbox.secret_provider import YandexLockboxSecretProvider
from infrastructure.max.max_client import MaxClient
from infrastructure.max.max_notification_channel import MaxNotificationChannel
from infrastructure.ydb.client import YdbClient, YdbConfig
from infrastructure.ydb.repositories import YdbProcessedEventRepository, YdbSubjectRepository, YdbSubscriptionRepository


class _Registry:
    def __init__(self, channel):
        self.channel = channel

    def get(self, name: str):
        return self.channel


TEST_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAvElEQVR4nO3aQQ6AIAwAwYj//9l4AymwM7FJNYk3bqUEKew+CTNmzJgxY8aMGTPm8OQDzrbt2+N9v9t7D6AB5yM4gAacj+AAAHgLwQEA8BaCAwDgLQQHAMBbCA4AgLcQHAAAbyE4AABeQnAAALyF4AAAeAvBAQDwFoIDeId3RrjP1rs0y9b0bQF7vLQAAHgLwQEA8BaCAwDgLQQHAMBbCA4AgLcQHAAAbyE4AABeQnAAALyF4AAAeAvBAQDwFoID+AAAM2bMmDFjxowZM3b8ALHfCq9mW5wYAAAAAElFTkSuQmCC"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-image", action="store_true")
    parser.add_argument("--user-id", default="")
    args = parser.parse_args()

    settings = load_settings()
    session = YdbClient(YdbConfig(settings.ydb_endpoint, settings.ydb_database)).session()
    subjects = YdbSubjectRepository(session)
    subscriptions = YdbSubscriptionRepository(session)
    processed = YdbProcessedEventRepository(session)
    notifier = NotificationService(
        processed,
        _Registry(MaxNotificationChannel(MaxClient(YandexLockboxSecretProvider(settings.env), settings.max_api_base_url))),
        CodeTemplateProvider(),
    )

    active = subscriptions.list_active()
    if args.user_id:
        active = [item for item in active if item.user_id == args.user_id]
    if not active:
        raise SystemExit("No active subscription found")
    subscription = active[0]
    subject = subjects.get_by_id(subscription.subject_id)
    if not subject:
        raise SystemExit("Subscription subject is missing")

    metadata = {"subject_title": subject.title}
    if args.with_image:
        metadata["image_bytes"] = TEST_PNG
    event = TaskEvent(
        external_id=f"manual-notification-test-{uuid4()}",
        subject_id=subject.subject_id,
        source=Source.SYSTEM,
        event_type=EventType.TEST_NOTIFICATION,
        occurred_at=datetime.now(UTC),
        metadata=metadata,
    )
    sent = notifier.notify_users(event, [subscription.user_id])
    print(json.dumps({"sent": sent, "user_id": subscription.user_id, "subject_id": subject.subject_id, "with_image": args.with_image}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
