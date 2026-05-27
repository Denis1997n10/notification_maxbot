from __future__ import annotations

import json
import logging
from typing import Any

from composition.container import api_response, build_container

logger = logging.getLogger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    container = build_container()
    payload = json.loads(event.get("body") or "{}")

    logger.info("bot_webhook_received", extra={"keys": list(payload.keys())[:10]})

    result = container.bot_service.handle_payload(payload)
    return api_response(200, result)
