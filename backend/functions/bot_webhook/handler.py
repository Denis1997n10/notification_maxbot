from __future__ import annotations

import json
import logging
from typing import Any

from composition.container import api_response, build_container

logger = logging.getLogger(__name__)


COMMANDS = {
    "my_subscriptions": "my_subscriptions",
    "add_address": "add_address",
    "remove_subscription": "remove_subscription",
    "disable_all": "disable_all",
    "services": "services",
    "help": "help",
}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    container = build_container()
    payload = json.loads(event.get("body") or "{}")
    text = (payload.get("text") or "").strip()

    logger.info("bot_webhook_received", extra={"has_text": bool(text)})

    if text.startswith("/start "):
        public_code = text.split(" ", 1)[1]
        result = container.bot_service.start_with_public_code(public_code)
        return api_response(200, result)

    action = COMMANDS.get(text)
    if action:
        result = container.bot_service.handle_action(action, payload)
        return api_response(200, result)

    return api_response(200, {"message": "help"})
