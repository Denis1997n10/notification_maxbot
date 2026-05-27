from __future__ import annotations

import logging
from typing import Any

from composition.container import api_response, build_container

logger = logging.getLogger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    container = build_container()
    logger.info("notification_sender_received")
    result = container.notification_service.send_batch(event)
    return api_response(200, {"ok": True, **(result or {})})
