from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from application.services import NotificationService
from application.use_cases.use_cases import ProcessExternalEventsUseCase


@dataclass
class AppContainer:
    bot_service: Any
    public_service: Any
    admin_service: Any
    polling_use_case: Any
    notification_service: NotificationService | Any


def build_container() -> AppContainer:
    return AppContainer(
        bot_service=None,
        public_service=None,
        admin_service=None,
        polling_use_case=ProcessExternalEventsUseCase(provider=None, notifier=None),
        notification_service=None,
    )


def api_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": __import__("json").dumps(body, ensure_ascii=False),
    }


def now_utc() -> datetime:
    return datetime.now(UTC)
