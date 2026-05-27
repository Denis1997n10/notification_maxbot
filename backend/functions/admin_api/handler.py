from __future__ import annotations

import logging
from typing import Any

from composition.container import api_response, build_container

logger = logging.getLogger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    container = build_container()
    path = event.get("path", "")
    method = event.get("httpMethod", "GET")

    logger.info("admin_api_request", extra={"path": path, "method": method})

    if method == "POST" and path == "/api/v1/admin/auth/login":
        result = container.admin_service.login(event.get("body"))
        return api_response(401 if "error" in result else 200, result)
    if method == "GET" and path == "/api/v1/admin/me":
        result = container.admin_service.me(event.get("headers") or {})
        return api_response(401 if "error" in result else 200, result)
    if method == "POST" and path == "/api/v1/admin/test-notification":
        result = container.admin_service.send_test_notification(event.get("headers") or {}, event.get("body"))
        status = 401 if result.get("error") == "unauthorized" else 400 if "error" in result else 200
        return api_response(status, result)

    return api_response(404, {"error": "not_found"})
