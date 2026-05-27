from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from composition.container import api_response, build_container, now_utc
from config.settings import load_settings

logger = logging.getLogger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    settings = load_settings()
    container = build_container()

    now = now_utc()
    date_from = now - timedelta(
        minutes=settings.polling_interval_minutes + settings.polling_overlap_minutes
    )

    result = asyncio.run(container.polling_use_case.execute(date_from=date_from, date_to=now))
    logger.info("regioncity_polling_done", extra={"date_from": date_from.isoformat(), "date_to": now.isoformat(), **(result or {})})
    return api_response(200, {"ok": True, **(result or {})})
