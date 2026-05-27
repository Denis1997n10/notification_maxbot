from __future__ import annotations

import json
import logging
import hmac
import os
from typing import Any

from composition.container import api_response, build_container
from domain.entities.models import NotificationPayload
from infrastructure.max.max_webhook_parser import MaxWebhookParser

logger = logging.getLogger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    configured_secret = os.getenv("MAX_WEBHOOK_SECRET", "")
    if os.getenv("ENV") == "prod" and not configured_secret:
        logger.error("max_webhook_secret_missing")
        return api_response(500, {"error": "configuration_error"})
    if configured_secret:
        headers = {str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items()}
        provided_secret = headers.get("x-max-bot-api-secret", "")
        if not hmac.compare_digest(configured_secret, provided_secret):
            return api_response(401, {"error": "unauthorized"})

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

    if container.bot_reply_channel and result.get("message"):
        user_id = MaxWebhookParser().external_user_id(payload)
        if user_id:
            container.bot_reply_channel.send(
                NotificationPayload(user_id=user_id, channel="max", title="", body=result["message"])
            )
    return api_response(200, result)
