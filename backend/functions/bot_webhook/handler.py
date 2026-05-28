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


def _webhook_updates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    updates = payload.get("updates")
    if isinstance(updates, list):
        return [item for item in updates if isinstance(item, dict)]
    update = payload.get("update")
    if isinstance(update, dict):
        return [update]
    return [payload]


def _handle_single_update(container: Any, payload: dict[str, Any]) -> dict[str, Any]:
    if hasattr(container.bot_service, "handle_payload"):
        return container.bot_service.handle_payload(payload)
    text = payload.get("text") or (payload.get("message") or {}).get("text") or ""
    if text.startswith("/start "):
        return container.bot_service.start_with_public_code(text.split(" ", 1)[1].strip())
    return container.bot_service.handle_action("help", payload)


def _send_reply(container: Any, payload: dict[str, Any], result: dict[str, Any]) -> None:
    if not container.bot_reply_channel or not result.get("message"):
        return
    parser = MaxWebhookParser()
    keyboard = result.get("keyboard")
    callback_id = parser.callback_id(payload)
    if callback_id and hasattr(container.bot_reply_channel, "answer_callback"):
        container.bot_reply_channel.answer_callback(callback_id, result["message"], keyboard=keyboard)
        return
    user_id = parser.external_user_id(payload)
    if user_id:
        metadata = {}
        if keyboard:
            metadata["keyboard"] = keyboard
        container.bot_reply_channel.send(
            NotificationPayload(user_id=user_id, channel="max", title="", body=result["message"], metadata=metadata)
        )


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

    results = []
    for update in _webhook_updates(payload):
        result = _handle_single_update(container, update)
        results.append(result)
        _send_reply(container, update, result)

    if len(results) == 1:
        return api_response(200, results[0])
    return api_response(200, {"items": results})
