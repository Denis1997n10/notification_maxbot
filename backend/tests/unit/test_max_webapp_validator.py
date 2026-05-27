import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from infrastructure.max.max_webapp_validator import MaxWebAppValidator


def signed_init_data(bot_token: str, params: dict) -> str:
    payload = dict(params)
    check_string = "\n".join(f"{key}={payload[key]}" for key in sorted(payload))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    payload["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(payload)


def test_webapp_validator_accepts_signed_user_data():
    token = "test-token"
    init_data = signed_init_data(
        token,
        {
            "auth_date": str(int(time.time())),
            "query_id": "q1",
            "user": json.dumps({"id": 42, "first_name": "Denis"}, separators=(",", ":")),
        },
    )

    user = MaxWebAppValidator(token).verify_user(init_data)

    assert user.external_user_id == "42"
    assert user.display_name == "Denis"


def test_webapp_validator_rejects_tampered_data():
    token = "test-token"
    init_data = signed_init_data(
        token,
        {
            "auth_date": str(int(time.time())),
            "user": json.dumps({"id": 42}, separators=(",", ":")),
        },
    ).replace("42", "43")

    assert MaxWebAppValidator(token).verify_user(init_data) is None
