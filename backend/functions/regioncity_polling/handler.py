from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from composition.container import api_response, build_container, now_utc
from config.settings import load_settings

logger = logging.getLogger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    event = _event_dict(event)
    settings = load_settings()
    container = build_container()

    now = now_utc()
    date_to = _parse_dt(event.get("date_to")) if event.get("date_to") else now
    date_from = _parse_dt(event.get("date_from")) if event.get("date_from") else date_to - timedelta(
        minutes=settings.polling_interval_minutes + settings.polling_overlap_minutes
    )
    notify = _parse_bool(event.get("notify", True))

    result = asyncio.run(container.polling_use_case.execute(date_from=date_from, date_to=date_to, notify=notify))
    logger.info("regioncity_polling_done", extra={"date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "notify": notify, **(result or {})})
    return api_response(200, {"ok": True, **(result or {})})


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _event_dict(event: Any) -> dict[str, Any]:
    if isinstance(event, dict):
        return event
    if isinstance(event, str) and event.strip():
        try:
            return json.loads(event)
        except json.JSONDecodeError:
            return _loose_event_dict(event)
    return {}


def _loose_event_dict(value: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for part in value.strip().strip("{}").split(","):
        if ":" not in part:
            continue
        key, raw = part.split(":", 1)
        normalized_key = key.strip().strip('"')
        normalized_value = raw.strip().strip('"')
        if normalized_key == "notify":
            result[normalized_key] = _parse_bool(normalized_value)
        else:
            result[normalized_key] = normalized_value
    return result
