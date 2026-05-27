from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import hmac
import json
from urllib.parse import parse_qsl


@dataclass(slots=True)
class MaxWebAppUser:
    external_user_id: str
    display_name: str = ""


class MaxWebAppValidator:
    def __init__(self, bot_token: str, max_age_seconds: int = 3600) -> None:
        self._bot_token = bot_token
        self._max_age_seconds = max_age_seconds

    def verify_user(self, init_data: str) -> MaxWebAppUser | None:
        params = dict(parse_qsl(init_data or "", keep_blank_values=True))
        received_hash = params.pop("hash", "")
        if not params or not received_hash:
            return None

        check_string = "\n".join(f"{key}={params[key]}" for key in sorted(params))
        secret_key = hmac.new(b"WebAppData", self._bot_token.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_hash, received_hash):
            return None

        if not self._fresh(params.get("auth_date")):
            return None

        try:
            user = json.loads(params.get("user") or "{}")
        except json.JSONDecodeError:
            return None
        external_user_id = str(user.get("id") or user.get("user_id") or "")
        if not external_user_id:
            return None
        display_name = " ".join(
            part
            for part in (
                str(user.get("first_name") or "").strip(),
                str(user.get("last_name") or "").strip(),
            )
            if part
        ) or str(user.get("username") or user.get("name") or "").strip()
        return MaxWebAppUser(external_user_id=external_user_id, display_name=display_name)

    def _fresh(self, auth_date: str | None) -> bool:
        try:
            issued_at = int(auth_date or "0")
        except ValueError:
            return False
        now = int(datetime.now(UTC).timestamp())
        return 0 < issued_at <= now and now - issued_at <= self._max_age_seconds
