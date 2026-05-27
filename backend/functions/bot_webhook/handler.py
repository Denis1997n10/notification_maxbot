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

    if hasattr(container.bot_service, "handle_payload"):
        result = container.bot_service.handle_payload(payload)
    else:
        text = payload.get("text") or (payload.get("message") or {}).get("text") or ""
        if text.startswith("/start "):
            result = container.bot_service.start_with_public_code(text.split(" ", 1)[1].strip())
        else:
            result = container.bot_service.handle_action("help", payload)
    return api_response(200, result)
