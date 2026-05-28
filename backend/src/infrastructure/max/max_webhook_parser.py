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
        callback_user = callback.get("user") or {}
        return str(
            sender.get("user_id")
            or sender.get("id")
            or user.get("user_id")
            or user.get("id")
            or callback.get("user_id")
            or callback.get("userId")
            or callback_user.get("user_id")
            or callback_user.get("id")
            or payload.get("user_id")
            or payload.get("chat_id")
            or ""
        )

    def display_name(self, payload: dict) -> str:
        message = payload.get("message") or {}
        sender = message.get("sender") or {}
        user = payload.get("user") or {}
        callback = payload.get("callback") or {}
        callback_user = callback.get("user") or {}
        return str(
            sender.get("name")
            or sender.get("display_name")
            or user.get("name")
            or user.get("display_name")
            or user.get("username")
            or callback_user.get("name")
            or callback_user.get("display_name")
            or callback_user.get("username")
            or ""
        )

    def parse_start_public_code(self, payload: dict) -> str | None:
        text = self.message_text(payload)
        if text.startswith("/start "):
            return text.split(" ", 1)[1]
        return None

    def parse_action(self, payload: dict) -> str | None:
        callback = self.callback_payload(payload)
        if callback:
            return callback
        text = self.message_text(payload)
        if text in {"my_subscriptions", "add_address", "remove_subscription", "disable_all", "services", "help"}:
            return text
        return None

    def callback_payload(self, payload: dict) -> str | None:
        callback = payload.get("callback") or {}
        button = callback.get("button") or {}
        candidates = (
            callback.get("payload"),
            callback.get("data"),
            callback.get("callback_data"),
            button.get("payload"),
            button.get("data"),
            button.get("callback_data"),
            payload.get("callback_payload"),
            payload.get("payload"),
            payload.get("data"),
        )
        for candidate in candidates:
            if candidate:
                return str(candidate).strip()
        return None
