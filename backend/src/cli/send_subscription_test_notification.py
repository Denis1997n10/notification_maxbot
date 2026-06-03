from __future__ import annotations

import argparse
import json
import struct
import zlib
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
from infrastructure.ydb.repositories import YdbProcessedEventRepository, YdbSubjectRepository, YdbSubscriptionRepository, YdbUserRepository


class _Registry:
    def __init__(self, channel):
        self.channel = channel

    def get(self, name: str):
        return self.channel


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _build_test_png(width: int = 160, height: int = 90) -> bytes:
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            row += bytes((0, 110 + (x % 40), 88 + (y % 80), 255))
        rows.append(bytes(row))
    raw = b"".join(rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )


TEST_PNG = _build_test_png()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-image", action="store_true")
    parser.add_argument("--user-id", default="")
    args = parser.parse_args()

    settings = load_settings()
    session = YdbClient(YdbConfig(settings.ydb_endpoint, settings.ydb_database)).session()
    subjects = YdbSubjectRepository(session)
    users = YdbUserRepository(session)
    subscriptions = YdbSubscriptionRepository(session)
    processed = YdbProcessedEventRepository(session)
    notifier = NotificationService(
        processed,
        _Registry(MaxNotificationChannel(MaxClient(YandexLockboxSecretProvider(settings.env), settings.max_api_base_url))),
        CodeTemplateProvider(),
        users,
    )

    active = subscriptions.list_active()
    if args.user_id:
        active = [item for item in active if item.user_id == args.user_id]
    if not active:
        raise SystemExit("No active subscription found")
    subscription = None
    subject = None
    for item in active:
        item_subject = subjects.get_by_id(item.subject_id)
        if item_subject:
            subscription = item
            subject = item_subject
            break
    if not subscription or not subject:
        raise SystemExit("No active subscription with an active subject found")

    metadata = {"subject_title": subject.title}
    if args.with_image:
        metadata["image_bytes"] = TEST_PNG
        metadata["require_image"] = True
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
