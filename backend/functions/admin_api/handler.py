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
        return api_response(200, container.admin_service.login(event.get("body")))
    if method == "GET" and path == "/api/v1/admin/me":
        return api_response(200, container.admin_service.me(event.get("headers") or {}))
    if method == "POST" and path == "/api/v1/admin/test-notification":
        return api_response(200, container.admin_service.send_test_notification(event.get("body")))

    return api_response(404, {"error": "not_found"})
