from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from composition.container import api_response, build_container
from config.settings import load_settings

logger = logging.getLogger(__name__)


COMMANDS = {
    "my_subscriptions": "my_subscriptions",
    "add_address": "add_address",
    "remove_subscription": "remove_subscription",
    "disable_all": "disable_all",
    "services": "services",
    "help": "help",
}


def _deep_get(data: dict[str, Any], path: list[str]) -> Any:
    current: Any = data
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _extract_text(payload: dict[str, Any]) -> str:
    candidates = [
        payload.get("text"),
        _deep_get(payload, ["message", "text"]),
        _deep_get(payload, ["message", "body", "text"]),
        _deep_get(payload, ["message", "body", "mid"]),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _extract_recipient(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    chat_candidates = [
        payload.get("chat_id"),
        _deep_get(payload, ["chat", "chat_id"]),
        _deep_get(payload, ["chat", "id"]),
        _deep_get(payload, ["message", "chat_id"]),
        _deep_get(payload, ["message", "chat", "chat_id"]),
        _deep_get(payload, ["message", "chat", "id"]),
        _deep_get(payload, ["message", "recipient", "chat_id"]),
        _deep_get(payload, ["message", "recipient", "id"]),
        _deep_get(payload, ["recipient", "chat_id"]),
        _deep_get(payload, ["recipient", "id"]),
    ]
    for candidate in chat_candidates:
        if candidate is not None:
            return "chat_id", str(candidate)

    user_candidates = [
        payload.get("user_id"),
        _deep_get(payload, ["user", "user_id"]),
        _deep_get(payload, ["user", "id"]),
        _deep_get(payload, ["sender", "user_id"]),
        _deep_get(payload, ["sender", "id"]),
        _deep_get(payload, ["message", "sender", "user_id"]),
        _deep_get(payload, ["message", "sender", "id"]),
        _deep_get(payload, ["message", "from", "user_id"]),
        _deep_get(payload, ["message", "from", "id"]),
        _deep_get(payload, ["message", "author", "user_id"]),
        _deep_get(payload, ["message", "author", "id"]),
    ]
    for candidate in user_candidates:
        if candidate is not None:
            return "user_id", str(candidate)

    return None, None


def _get_max_token() -> str | None:
    direct = os.getenv("MAX_BOT_TOKEN")
    if direct:
        return direct

    secret_id = os.getenv("MAX_BOT_TOKEN_SECRET_ID")
    if not secret_id:
        return None

    try:
        from yandexcloud import SDK
        from yandex.cloud.lockbox.v1.payload_service_pb2 import GetPayloadRequest
        from yandex.cloud.lockbox.v1.payload_service_pb2_grpc import PayloadServiceStub

        sdk = SDK()
        client = sdk.client(PayloadServiceStub)
        payload = client.Get(GetPayloadRequest(secret_id=secret_id))
        for entry in payload.entries:
            if entry.key == "MAX_BOT_TOKEN":
                return entry.text_value
    except Exception as exc:
        logger.exception("max_token_load_failed", extra={"error_type": type(exc).__name__})
        return None

    return None


def _send_max_text(payload: dict[str, Any], text: str) -> bool:
    recipient_type, recipient_id = _extract_recipient(payload)
    if not recipient_type or not recipient_id:
        logger.warning("max_reply_skipped_no_recipient")
        return False

    token = _get_max_token()
    if not token:
        logger.warning("max_reply_skipped_no_token")
        return False

    settings = load_settings()
    base_url = (settings.max_api_base_url or "https://platform-api.max.ru").rstrip("/")
    if "botapi.max.ru" in base_url:
        # Subscriptions and message APIs are available through platform-api.max.ru.
        base_url = "https://platform-api.max.ru"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{base_url}/messages",
                headers={"Authorization": token, "Content-Type": "application/json"},
                params={recipient_type: recipient_id},
                json={"text": text},
            )
        logger.info(
            "max_reply_sent",
            extra={
                "recipient_type": recipient_type,
                "status_code": response.status_code,
                "response_preview": response.text[:300],
            },
        )
        return response.status_code < 400
    except Exception as exc:
        logger.exception("max_reply_failed", extra={"error_type": type(exc).__name__})
        return False


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    container = build_container()
    payload = json.loads(event.get("body") or "{}")
    text = _extract_text(payload)

    logger.info(
        "bot_webhook_received",
        extra={
            "has_text": bool(text),
            "payload_preview": json.dumps(payload, ensure_ascii=False)[:1000],
        },
    )

    if text.startswith("/start "):
        public_code = text.split(" ", 1)[1]
        result = container.bot_service.start_with_public_code(public_code)
        sent = _send_max_text(payload, "Привет! Бот получил ссылку на подъезд. Сейчас включён dev smoke-режим, поэтому настоящая подписка пока не сохраняется.")
        return api_response(200, {"result": result, "sent": sent})

    if text == "/start":
        sent = _send_max_text(payload, "Привет! Бот подключен и получил /start. Сейчас включён dev smoke-режим.")
        return api_response(200, {"message": "start", "sent": sent})

    action = COMMANDS.get(text)
    if action:
        result = container.bot_service.handle_action(action, payload)
        sent = _send_max_text(payload, f"Команда '{text}' получена. Сейчас включён dev smoke-режим.")
        return api_response(200, {"result": result, "sent": sent})

    sent = _send_max_text(payload, "Бот получил сообщение. Сейчас включён dev smoke-режим.")
    return api_response(200, {"message": "help", "sent": sent})
