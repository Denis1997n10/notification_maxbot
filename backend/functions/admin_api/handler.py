from __future__ import annotations

import json
import logging
import os
from typing import Any

from composition.container import api_response, build_container

logger = logging.getLogger(__name__)


def _is_mock_mode() -> bool:
    return os.getenv("USE_MOCKS", "false").lower() == "true" or os.getenv("ENV") == "dev"


def _mock_admin_response(path: str, method: str, event: dict[str, Any]) -> dict[str, Any] | None:
    if not _is_mock_mode():
        return None

    if method == "POST" and path == "/api/v1/admin/auth/login":
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            body = {}
        login = body.get("login") or "admin"
        return api_response(
            200,
            {
                "token": "dev-mock-admin-token",
                "role": "super_admin",
                "login": login,
                "mock": True,
            },
        )

    if method == "GET" and path == "/api/v1/admin/me":
        return api_response(
            200,
            {
                "id": "dev-admin",
                "login": "admin",
                "role": "super_admin",
                "districts": [],
                "mock": True,
            },
        )

    if method == "POST" and path == "/api/v1/admin/test-notification":
        return api_response(200, {"status": "accepted", "mock": True, "action": "send_test_notification"})

    return None


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    container = build_container()
    path = event.get("path", "")
    method = event.get("httpMethod", "GET")

    logger.info("admin_api_request", extra={"path": path, "method": method})

    mock_response = _mock_admin_response(path, method, event)
    if mock_response is not None:
        return mock_response

    if method == "POST" and path == "/api/v1/admin/auth/login":
        return api_response(200, container.admin_service.login(event.get("body")))
    if method == "GET" and path == "/api/v1/admin/me":
        return api_response(200, container.admin_service.me(event.get("headers") or {}))
    if method == "POST" and path == "/api/v1/admin/test-notification":
        return api_response(200, container.admin_service.send_test_notification(event.get("body")))

    return api_response(404, {"error": "not_found"})
