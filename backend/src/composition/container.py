from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import os
from typing import Any


@dataclass
class AppContainer:
    bot_service: Any
    public_service: Any
    admin_service: Any
    polling_use_case: Any
    notification_service: Any


def _not_implemented(name: str) -> Any:
    raise NotImplementedError(f"Composition dependency '{name}' is not configured for ENV={os.getenv('ENV', 'local')}")


def build_container() -> AppContainer:
    if os.getenv("ENV", "local") == "local" or os.getenv("USE_MOCKS", "false").lower() == "true":
        class _Mock:
            def __getattr__(self, item):
                def _(*args, **kwargs):
                    return {"mock": True, "action": item}
                return _
        m = _Mock()
        return AppContainer(bot_service=m, public_service=m, admin_service=m, polling_use_case=m, notification_service=m)

    _not_implemented("runtime wiring")


def api_response(status: int, body: dict) -> dict:
    import json
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body, ensure_ascii=False)}


def now_utc() -> datetime:
    return datetime.now(UTC)
