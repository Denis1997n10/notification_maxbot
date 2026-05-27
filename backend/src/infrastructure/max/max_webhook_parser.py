from __future__ import annotations


class MaxWebhookParser:
    def message_text(self, payload: dict) -> str:
        message = payload.get("message") or {}
        body = message.get("body") or {}
        return str(body.get("text") or message.get("text") or payload.get("text") or "").strip()

    def external_user_id(self, payload: dict) -> str:
        message = payload.get("message") or {}
        sender = message.get("sender") or {}
        user = payload.get("user") or {}
        callback = payload.get("callback") or {}
        return str(
            sender.get("user_id")
            or sender.get("id")
            or user.get("user_id")
            or user.get("id")
            or callback.get("user_id")
            or payload.get("user_id")
            or payload.get("chat_id")
            or ""
        )

    def display_name(self, payload: dict) -> str:
        message = payload.get("message") or {}
        sender = message.get("sender") or {}
        user = payload.get("user") or {}
        return str(
            sender.get("name")
            or sender.get("display_name")
            or user.get("name")
            or user.get("display_name")
            or user.get("username")
            or ""
        )

    def parse_start_public_code(self, payload: dict) -> str | None:
        text = self.message_text(payload)
        if text.startswith("/start "):
            return text.split(" ", 1)[1]
        return None

    def parse_action(self, payload: dict) -> str | None:
        callback = (payload.get("callback") or {}).get("data")
        if callback:
            return callback
        text = self.message_text(payload)
        if text in {"my_subscriptions", "add_address", "remove_subscription", "disable_all", "services", "help"}:
            return text
        return None
