from __future__ import annotations


class MaxWebhookParser:
    def parse_start_public_code(self, payload: dict) -> str | None:
        text = ((payload.get("message") or {}).get("text") or payload.get("text") or "").strip()
        if text.startswith("/start "):
            return text.split(" ", 1)[1]
        return None

    def parse_action(self, payload: dict) -> str | None:
        callback = (payload.get("callback") or {}).get("data")
        if callback:
            return callback
        text = ((payload.get("message") or {}).get("text") or payload.get("text") or "").strip()
        if text in {"my_subscriptions", "add_address", "remove_subscription", "disable_all", "services", "help"}:
            return text
        return None
